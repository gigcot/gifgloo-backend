from payment.application.ports.outbound.domain_bridges.user_verification_port import (
    UserVerificationPort,
)
from user.application.services.async_verify_user_service import AsyncVerifyUserService


class AsyncUserVerificationAdapter(UserVerificationPort):
    def __init__(self, service: AsyncVerifyUserService):
        self._service = service

    async def is_active_user(self, user_id: str) -> bool:
        return await self._service.execute(user_id)
