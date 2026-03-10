from typing import Optional

from sqlalchemy.orm import Session

from composition.adapter.outbound.persistence.models import CompositionJobModel, CompositionFrameModel
from composition.application.ports.outbound.composition_repository import CompositionRepository
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.entities.composition_frame import CompositionFrame
from composition.domain.value_objects.composition_image import CompositionImage, ImageRole, ImageFormat
from composition.domain.value_objects.composition_status import CompositionStatus
from composition.domain.value_objects.composition_type import CompositionType, CompositionTypeValue


class SqlAlchemyCompositionRepository(CompositionRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, job: CompositionJob) -> None:
        existing = self._session.get(CompositionJobModel, job.id)
        if existing:
            existing.status = job.status.value
            existing.result_asset_id = job.result_asset_id
            existing.failed_reason = job.failed_reason
            existing_frame_ids = {f.id for f in existing.frames}
            for frame in job.frames:
                if frame.id in existing_frame_ids:
                    for m in existing.frames:
                        if m.id == frame.id:
                            m.status = frame.status.value
                            m.result_asset_id = frame.result_asset_id
                            m.failed_reason = frame.failed_reason
                else:
                    existing.frames.append(self._frame_to_model(frame, job.id))
        else:
            model = CompositionJobModel(
                id=job.id,
                user_id=job.user_id,
                base_image_asset_id=job.base_image.asset_id,
                base_image_role=job.base_image.role.value,
                base_image_format=job.base_image.format.value,
                overlay_image_asset_id=job.overlay_image.asset_id,
                overlay_image_role=job.overlay_image.role.value,
                overlay_image_format=job.overlay_image.format.value,
                type=job.type.value.value,
                status=job.status.value,
                result_asset_id=job.result_asset_id,
                failed_reason=job.failed_reason,
                created_at=job.created_at,
                frames=[self._frame_to_model(f, job.id) for f in job.frames],
            )
            self._session.add(model)
        self._session.commit()

    def find_by_id(self, job_id: str) -> Optional[CompositionJob]:
        model = self._session.get(CompositionJobModel, job_id)
        return self._to_domain(model) if model else None

    def _frame_to_model(self, frame: CompositionFrame, job_id: str) -> CompositionFrameModel:
        return CompositionFrameModel(
            id=frame.id,
            job_id=job_id,
            frame_index=frame.frame_index,
            status=frame.status.value,
            result_asset_id=frame.result_asset_id,
            failed_reason=frame.failed_reason,
        )

    def _to_domain(self, model: CompositionJobModel) -> CompositionJob:
        job = object.__new__(CompositionJob)
        job.id = model.id
        job.user_id = model.user_id
        job.base_image = CompositionImage(
            asset_id=model.base_image_asset_id,
            role=ImageRole(model.base_image_role),
            format=ImageFormat(model.base_image_format),
        )
        job.overlay_image = CompositionImage(
            asset_id=model.overlay_image_asset_id,
            role=ImageRole(model.overlay_image_role),
            format=ImageFormat(model.overlay_image_format),
        )
        job.type = CompositionType(value=CompositionTypeValue(model.type))
        job.status = CompositionStatus(model.status)
        job.result_asset_id = model.result_asset_id
        job.failed_reason = model.failed_reason
        job.created_at = model.created_at
        job.frames = [self._frame_to_domain(f) for f in model.frames]
        return job

    def _frame_to_domain(self, model: CompositionFrameModel) -> CompositionFrame:
        frame = object.__new__(CompositionFrame)
        frame.id = model.id
        frame.frame_index = model.frame_index
        frame.status = CompositionStatus(model.status)
        frame.result_asset_id = model.result_asset_id
        frame.failed_reason = model.failed_reason
        return frame
