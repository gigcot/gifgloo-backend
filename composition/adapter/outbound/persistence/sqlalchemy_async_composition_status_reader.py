from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.models import CompositionJobModel
from composition.application.ports.outbound.persistence.async_composition_status_reader import (
    AsyncCompositionStatusReader,
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


class SqlAlchemyAsyncCompositionStatusReader(AsyncCompositionStatusReader):
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory

    async def find_by_id(self, job_id: str) -> CompositionJob | None:
        async with self._session_factory() as session:
            model = await session.get(CompositionJobModel, job_id)
            if not model:
                return None
            return _to_domain(model)
