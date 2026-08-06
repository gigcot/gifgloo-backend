from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.outbound.domain_bridges.user_admin_lookup_adapter import (
    UserAdminLookupAdapter,
)
from admin.application.ports.outbound.domain_bridges.user_admin_lookup_port import (
    UserAdminLookupPort,
)
from config.database import get_async_db
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import (
    SqlAlchemyAsyncUserRepository,
)
from user.application.services.async_get_user_admin_summary_service import (
    AsyncGetUserAdminSummaryService,
)


def get_user_admin_lookup_port(
    db: AsyncSession = Depends(get_async_db),
) -> UserAdminLookupPort:
    service = AsyncGetUserAdminSummaryService(SqlAlchemyAsyncUserRepository(db))
    return UserAdminLookupAdapter(service)
