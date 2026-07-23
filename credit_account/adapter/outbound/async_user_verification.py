from credit_account.application.ports.outbound.async_user_verification_port import (
    AsyncUserVerificationPort,
)
from user.application.services.async_verify_user_service import AsyncVerifyUserService


class AsyncUserVerificationAdapter(AsyncUserVerificationPort):
    def __init__(self, verify_user_service: AsyncVerifyUserService):
        self._verify_user_service = verify_user_service

    async def is_active_user(self, user_id: str) -> bool:
        return await self._verify_user_service.execute(user_id)
