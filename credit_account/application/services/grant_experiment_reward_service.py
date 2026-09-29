from datetime import timedelta

from credit_account.application.ports.inbound.grant_experiment_reward import (
    GrantExperimentRewardCommand,
)
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.credit_policy import CreditPolicy
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import NotFoundException


class GrantExperimentRewardService:
    def __init__(self, credit_account_repo: AsyncCreditAccountRepository):
        self._credit_account_repo = credit_account_repo

    async def execute(self, command: GrantExperimentRewardCommand) -> None:
        account = await self._credit_account_repo.find_for_update(command.user_id)
        if account is None:
            raise NotFoundException("이용권 계정을 찾을 수 없습니다")

        existing = await self._credit_account_repo.find_transaction_by_source(
            user_id=command.user_id,
            transaction_type=TransactionType.CHARGE,
            source_type=CreditSourceType.EXPERIMENT,
            source_id=command.response_id,
        )
        if existing is not None:
            return

        account.charge(
            amount=CreditAccount.composition_cost,
            source_type=CreditSourceType.EXPERIMENT,
            source_id=command.response_id,
            reason="EXP-001 설문 참여 보상",
            granted_at=command.granted_at,
            expires_at=command.granted_at
            + timedelta(days=CreditPolicy.PASS_VALIDITY_DAYS),
        )
        await self._credit_account_repo.save(account)
