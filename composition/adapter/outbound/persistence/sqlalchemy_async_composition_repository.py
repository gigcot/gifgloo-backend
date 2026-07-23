from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.models import CompositionJobModel
from composition.application.ports.outbound.persistence.async_composition_repository import (
    AsyncCompositionRepository,
)
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_stage import CompositionStage
from composition.domain.value_objects.composition_status import CompositionStatus


def _to_domain(model: CompositionJobModel) -> CompositionJob:
    job = object.__new__(CompositionJob)
    job.id = model.id
    job.user_id = model.user_id
    job.status = CompositionStatus(model.status)
    job.stage = CompositionStage(model.stage) if model.stage else None
    job.gif_url = model.gif_url
    job.source_gif_url = model.source_gif_url
    job.target_url = model.target_url
    job.source_gif_asset_id = model.source_gif_asset_id
    job.target_asset_id = model.target_asset_id
    job.draft_asset_id = model.draft_asset_id
    job.result_asset_id = model.result_asset_id
    job.result_url = model.result_url
    job.failed_reason = model.failed_reason
    job.durations_ms = model.durations_ms
    job.spec = model.spec
    job.created_at = model.created_at
    return job


class SqlAlchemyAsyncCompositionRepository(AsyncCompositionRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, job: CompositionJob) -> None:
        self._session.add(CompositionJobModel(
            id=job.id,
            user_id=job.user_id,
            status=job.status.value,
            stage=job.stage.value if job.stage else None,
            gif_url=job.gif_url,
            source_gif_url=job.source_gif_url,
            target_url=job.target_url,
            source_gif_asset_id=job.source_gif_asset_id,
            target_asset_id=job.target_asset_id,
            draft_asset_id=job.draft_asset_id,
            result_asset_id=job.result_asset_id,
            result_url=job.result_url,
            failed_reason=job.failed_reason,
            durations_ms=job.durations_ms,
            spec=job.spec,
            created_at=job.created_at,
        ))
        await self._session.flush()

    async def update(self, job: CompositionJob) -> None:
        await self._session.execute(
            update(CompositionJobModel)
            .where(CompositionJobModel.id == job.id)
            .values(
                status=job.status.value,
                stage=job.stage.value if job.stage else None,
                gif_url=job.gif_url,
                source_gif_url=job.source_gif_url,
                target_url=job.target_url,
                source_gif_asset_id=job.source_gif_asset_id,
                target_asset_id=job.target_asset_id,
                draft_asset_id=job.draft_asset_id,
                result_asset_id=job.result_asset_id,
                result_url=job.result_url,
                failed_reason=job.failed_reason,
                durations_ms=job.durations_ms,
                spec=job.spec,
            )
        )
        await self._session.flush()

    async def find_for_update(self, job_id: str) -> CompositionJob | None:
        statement = (
            select(CompositionJobModel)
            .where(CompositionJobModel.id == job_id)
            .with_for_update()
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_all_by_user_id(
        self,
        user_id: str,
        limit: int,
        offset: int,
    ) -> list[CompositionJob]:
        statement = (
            select(CompositionJobModel)
            .where(CompositionJobModel.user_id == user_id)
            .order_by(CompositionJobModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        models = (await self._session.scalars(statement)).all()
        return [_to_domain(model) for model in models]
