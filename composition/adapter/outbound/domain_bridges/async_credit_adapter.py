from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from credit_account.application.services.async_credit_service import AsyncCreditService


class AsyncCreditAdapter(CreditPort):
    def __init__(self, service: AsyncCreditService):
        self._service = service

    async def has_enough_credit(self, user_id: str) -> bool:
        return await self._service.has_enough_credit(user_id)

    async def deduct(self, user_id: str, job_id: str) -> None:
        await self._service.deduct(user_id, job_id)

    async def refund(self, user_id: str, job_id: str) -> None:
        await self._service.refund(user_id, job_id)
