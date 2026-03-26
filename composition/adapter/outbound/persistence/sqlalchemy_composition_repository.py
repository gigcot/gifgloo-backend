from typing import Optional

from sqlalchemy.orm import Session

from composition.adapter.outbound.persistence.models import CompositionJobModel
from composition.application.ports.outbound.persistence.composition_repository import CompositionRepository
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_status import CompositionStatus


class SqlAlchemyCompositionRepository(CompositionRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, job: CompositionJob) -> None:
        existing = self._session.get(CompositionJobModel, job.id)
        if existing:
            existing.status = job.status.value
            existing.source_gif_asset_id = job.source_gif_asset_id
            existing.target_asset_id = job.target_asset_id
            existing.draft_asset_id = job.draft_asset_id
            existing.result_asset_id = job.result_asset_id
            existing.result_url = job.result_url
            existing.failed_reason = job.failed_reason
        else:
            self._session.add(CompositionJobModel(
                id=job.id,
                user_id=job.user_id,
                status=job.status.value,
                source_gif_asset_id=job.source_gif_asset_id,
                target_asset_id=job.target_asset_id,
                draft_asset_id=job.draft_asset_id,
                result_asset_id=job.result_asset_id,
                result_url=job.result_url,
                failed_reason=job.failed_reason,
                created_at=job.created_at,
            ))
        self._session.commit()

    def find_by_id(self, job_id: str) -> Optional[CompositionJob]:
        model = self._session.get(CompositionJobModel, job_id)
        if not model:
            return None
        job = object.__new__(CompositionJob)
        job.id = model.id
        job.user_id = model.user_id
        job.status = CompositionStatus(model.status)
        job.source_gif_asset_id = model.source_gif_asset_id
        job.target_asset_id = model.target_asset_id
        job.draft_asset_id = model.draft_asset_id
        job.result_asset_id = model.result_asset_id
        job.result_url = model.result_url
        job.failed_reason = model.failed_reason
        job.created_at = model.created_at
        return job
