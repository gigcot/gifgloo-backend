from credit_account.application.ports.inbound.grant_experiment_reward import (
    GrantExperimentRewardCommand as CreditGrantExperimentRewardCommand,
)
from credit_account.application.services.grant_experiment_reward_service import (
    GrantExperimentRewardService,
)
from experiment.application.ports.outbound.domain_bridges.credit_reward_port import (
    CreditRewardPort,
    GrantExperimentRewardCommand,
)


class CreditRewardAdapter(CreditRewardPort):
    def __init__(self, service: GrantExperimentRewardService):
        self._service = service

    async def grant(self, command: GrantExperimentRewardCommand) -> None:
        await self._service.execute(
            CreditGrantExperimentRewardCommand(
                user_id=command.user_id,
                response_id=command.response_id,
                granted_at=command.granted_at,
            )
        )
