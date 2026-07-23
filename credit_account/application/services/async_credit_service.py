from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.application.ports.outbound.async_user_verification_port import (
    AsyncUserVerificationPort,
)
from shared.exceptions import AuthorizationException


class AsyncCreditService:
    def __init__(
        self,
        user_verification: AsyncUserVerificationPort,
        credit_account_repo: AsyncCreditAccountRepository,
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo

    async def has_enough_credit(self, user_id: str) -> bool:
        credit_account = await self._credit_account_repo.find_balance_by_user_id(user_id)
        return credit_account.has_enough()

    async def deduct(self, user_id: str) -> None:
        if not await self._user_verification.is_active_user(user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        credit_account = await self._credit_account_repo.find_for_update(user_id)
        credit_account.deduct()
        await self._credit_account_repo.save(credit_account)

    async def refund(self, user_id: str) -> None:
        credit_account = await self._credit_account_repo.find_for_update(user_id)
        credit_account.refund()
        await self._credit_account_repo.save(credit_account)
