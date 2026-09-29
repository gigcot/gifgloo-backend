from composition.application.services.has_completed_composition_service import (
    HasCompletedCompositionService,
)
from experiment.application.ports.outbound.domain_bridges.composition_completion_port import (
    CompositionCompletionPort,
)


class CompositionCompletionAdapter(CompositionCompletionPort):
    def __init__(self, service: HasCompletedCompositionService):
        self._service = service

    async def has_completed(self, user_id: str) -> bool:
        return await self._service.execute(user_id)
