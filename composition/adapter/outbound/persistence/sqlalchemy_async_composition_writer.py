from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.models import CompositionJobModel
from composition.application.ports.outbound.persistence.async_composition_writer import AsyncCompositionWriter
from composition.domain.aggregates.composition_job import CompositionJob


class SqlAlchemyAsyncCompositionWriter(AsyncCompositionWriter):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, job: CompositionJob) -> None:
        existing = await self._session.get(CompositionJobModel, job.id)
        if existing:
            existing.status = job.status.value
            existing.stage = job.stage.value if job.stage else None
            existing.gif_url = job.gif_url
            existing.source_gif_url = job.source_gif_url
            existing.target_url = job.target_url
            existing.source_gif_asset_id = job.source_gif_asset_id
            existing.target_asset_id = job.target_asset_id
            existing.draft_asset_id = job.draft_asset_id
            existing.result_asset_id = job.result_asset_id
            existing.result_url = job.result_url
            existing.failed_reason = job.failed_reason
            existing.durations_ms = job.durations_ms
            existing.spec = job.spec
        else:
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
