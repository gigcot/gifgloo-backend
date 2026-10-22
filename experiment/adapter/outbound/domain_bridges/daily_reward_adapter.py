from dataclasses import asdict
from datetime import datetime, timezone

from credit_account.application.ports.inbound.daily_credit_reward import DailyCreditRewardCommand
from credit_account.application.services.daily_credit_reward_service import DailyCreditRewardService
from experiment.application.ports.outbound.domain_bridges.daily_reward_port import DailyRewardPort, DailyRewardResult


class DailyRewardAdapter(DailyRewardPort):
    def __init__(self, service: DailyCreditRewardService):
        self._service = service

    async def get_status(self, user_id: str) -> DailyRewardResult:
        result = await self._service.get_status(DailyCreditRewardCommand(user_id, datetime.now(timezone.utc)))
        return DailyRewardResult(**asdict(result))

    async def claim(self, user_id: str) -> DailyRewardResult:
        result = await self._service.claim(DailyCreditRewardCommand(user_id, datetime.now(timezone.utc)))
        return DailyRewardResult(**asdict(result))
