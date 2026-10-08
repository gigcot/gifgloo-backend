from dataclasses import dataclass

from shared.exceptions import AuthenticationException
from user.application.ports.outbound.async_user_repository import AsyncUserRepository


@dataclass
class VerifiedSessionResult:
    user_kind: str
    consent_required: bool


class VerifySessionService:
    def __init__(self, users: AsyncUserRepository):
        self._users = users

    async def execute(self, user_id: str, session_version: int) -> VerifiedSessionResult:
        user = await self._users.find_by_id(user_id)
        if user is None or not user.is_active() or user.session_version != session_version:
            raise AuthenticationException("세션이 만료되었거나 변경되었습니다")
        return VerifiedSessionResult(user.user_kind, user.consent_required)
