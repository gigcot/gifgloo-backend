from composition.application.ports.outbound.persistence.async_composition_repository import (
    AsyncCompositionRepository,
)


class HasCompletedCompositionService:
    def __init__(self, composition_repo: AsyncCompositionRepository):
        self._composition_repo = composition_repo

    async def execute(self, user_id: str) -> bool:
        return await self._composition_repo.exists_completed_by_user_id(user_id)
