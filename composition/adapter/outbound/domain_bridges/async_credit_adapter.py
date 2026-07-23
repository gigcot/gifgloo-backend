from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from credit_account.application.services.async_credit_service import AsyncCreditService


class AsyncCreditAdapter(CreditPort):
    def __init__(self, credit_service: AsyncCreditService):
        self._credit_service = credit_service

    async def has_enough_credit(self, user_id: str) -> bool:
        return await self._credit_service.has_enough_credit(user_id)

    async def deduct(self, user_id: str) -> None:
        await self._credit_service.deduct(user_id)

    async def refund(self, user_id: str) -> None:
        await self._credit_service.refund(user_id)
