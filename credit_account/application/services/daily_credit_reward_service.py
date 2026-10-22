from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from credit_account.application.ports.inbound.daily_credit_reward import (
    DailyCreditRewardCommand,
    DailyCreditRewardResult,
)
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import CreditAccount, CreditTransaction
from credit_account.domain.value_objects.credit_policy import CreditPolicy
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import NotFoundException

KOREA = ZoneInfo("Asia/Seoul")


class DailyCreditRewardService:
    def __init__(self, repository: AsyncCreditAccountRepository):
        self._repository = repository

    async def get_status(self, command: DailyCreditRewardCommand) -> DailyCreditRewardResult:
        existing = await self._find_claim(command)
        return self._result(command, existing.created_at if existing else None, False)

    async def claim(self, command: DailyCreditRewardCommand) -> DailyCreditRewardResult:
        account = await self._repository.find_for_update(command.user_id)
        if account is None:
            raise NotFoundException("이용권 계정을 찾을 수 없습니다")
        existing = await self._find_claim(command)
        if existing is not None:
            return self._result(command, existing.created_at, False)

        result = self._result(command, command.requested_at, True)
        account.charge(
            amount=CreditAccount.composition_cost * CreditPolicy.DAILY_REWARD_USES,
            source_type=CreditSourceType.DAILY_REWARD,
            source_id=f"{command.user_id}:{result.claim_date}",
            reason="매일 3회 받기",
            granted_at=command.requested_at,
            expires_at=command.requested_at + timedelta(days=CreditPolicy.PASS_VALIDITY_DAYS),
        )
        await self._repository.save(account)
        return result

    async def _find_claim(self, command: DailyCreditRewardCommand) -> CreditTransaction | None:
        day = command.requested_at.astimezone(KOREA).date().isoformat()
        return await self._repository.find_transaction_by_source(
            user_id=command.user_id,
            transaction_type=TransactionType.CHARGE,
            source_type=CreditSourceType.DAILY_REWARD,
            source_id=f"{command.user_id}:{day}",
        )

    @staticmethod
    def _result(
        command: DailyCreditRewardCommand,
        claimed_at: datetime | None,
        granted: bool,
    ) -> DailyCreditRewardResult:
        day = command.requested_at.astimezone(KOREA).date()
        return DailyCreditRewardResult(
            claim_date=day.isoformat(),
            claimed=claimed_at is not None,
            granted=granted,
            server_now=command.requested_at,
            next_claim_at=datetime.combine(day + timedelta(days=1), time(), KOREA).astimezone(timezone.utc),
            expires_at=claimed_at + timedelta(days=CreditPolicy.PASS_VALIDITY_DAYS) if claimed_at else None,
        )
