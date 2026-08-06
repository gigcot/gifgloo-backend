from user.application.ports.inbound.get_user_admin_summary import (
    GetUserAdminSummaryCommand,
    GetUserAdminSummaryPort,
    GetUserAdminSummaryResult,
)
from user.application.ports.outbound.async_user_repository import AsyncUserRepository


class AsyncGetUserAdminSummaryService(GetUserAdminSummaryPort):
    def __init__(self, user_repo: AsyncUserRepository):
        self._user_repo = user_repo

    async def execute(
        self,
        command: GetUserAdminSummaryCommand,
    ) -> GetUserAdminSummaryResult | None:
        user = await self._user_repo.find_by_id(command.user_id)
        if user is None:
            return None
        return GetUserAdminSummaryResult(
            user_id=user.id,
            email=user.email.value if user.email else None,
            is_active=user.is_active(),
        )
