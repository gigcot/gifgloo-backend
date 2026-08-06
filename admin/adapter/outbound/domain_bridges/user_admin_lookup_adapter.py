from admin.application.ports.outbound.domain_bridges.user_admin_lookup_port import (
    AdminUserResult,
    UserAdminLookupPort,
)
from user.application.ports.inbound.get_user_admin_summary import (
    GetUserAdminSummaryCommand,
)
from user.application.services.async_get_user_admin_summary_service import (
    AsyncGetUserAdminSummaryService,
)


class UserAdminLookupAdapter(UserAdminLookupPort):
    def __init__(self, service: AsyncGetUserAdminSummaryService):
        self._service = service

    async def find_by_id(self, user_id: str) -> AdminUserResult | None:
        result = await self._service.execute(GetUserAdminSummaryCommand(user_id=user_id))
        if result is None:
            return None
        return AdminUserResult(
            user_id=result.user_id,
            email=result.email,
            is_active=result.is_active,
        )
