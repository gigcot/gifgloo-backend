from datetime import datetime, timezone

from credit_account.application.ports.outbound.async_user_verification_port import AsyncUserVerificationPort
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.application.ports.inbound.get_balance import (
    GetCreditBalanceCommand,
    GetCreditBalancePort,
    GetCreditBalanceResult,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from shared.exceptions import AuthorizationException, NotFoundException


class GetCreditBalanceService(GetCreditBalancePort):
    def __init__(
        self,
        user_verification: AsyncUserVerificationPort,
        credit_account_repo: AsyncCreditAccountRepository,
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo

    async def execute(
        self,
        command: GetCreditBalanceCommand,
    ) -> GetCreditBalanceResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        summary = await self._credit_account_repo.find_available_summary_by_user_id(
            command.user_id,
            datetime.now(timezone.utc),
        )
        if summary is None:
            raise NotFoundException("이용권 계정을 찾을 수 없습니다")

        return GetCreditBalanceResult(
            balance=summary.balance,
            remaining_uses=summary.balance // CreditAccount.composition_cost,
            nearest_expires_at=summary.nearest_expires_at,
        )
