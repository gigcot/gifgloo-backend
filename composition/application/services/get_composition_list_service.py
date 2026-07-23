from dataclasses import dataclass

from composition.application.ports.outbound.persistence.async_composition_repository import (
    AsyncCompositionRepository,
)
from composition.domain.value_objects.composition_status import CompositionStatus


@dataclass
class CompositionJobSummary:
    job_id: str
    status: CompositionStatus
    source_gif_url: str | None
    target_url: str | None
    result_url: str | None
    created_at: str


class GetCompositionListService:
    def __init__(self, composition_repo: AsyncCompositionRepository):
        self._composition_repo = composition_repo

    async def execute(
        self,
        user_id: str,
        limit: int,
        offset: int,
    ) -> list[CompositionJobSummary]:
        jobs = await self._composition_repo.find_all_by_user_id(user_id, limit, offset)
        return [
            CompositionJobSummary(
                job_id=job.id,
                status=job.status,
                source_gif_url=job.source_gif_url,
                target_url=job.target_url,
                result_url=job.result_url,
                created_at=job.created_at.isoformat(),
            )
            for job in jobs
        ]
