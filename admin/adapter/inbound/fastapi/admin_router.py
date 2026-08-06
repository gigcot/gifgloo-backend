import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.outbound.persistence.sqlalchemy_admin_ops_query import (
    SqlAlchemyAdminOpsQuery,
)
from admin.application.ports.outbound.domain_bridges.user_admin_lookup_port import (
    UserAdminLookupPort,
)
from admin.application.services.admin_ops_service import AdminOpsService
from config.admin import get_user_admin_lookup_port
from config.database import get_async_db
from config.payment import _get_toss_pay_gateway
from shared.exceptions import BusinessRuleException, NotFoundException

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _admin_panel_path() -> str:
    raw = os.getenv("ADMIN_PANEL_PATH", "").strip()
    if not raw:
        return "/admin-disabled"
    return raw if raw.startswith("/") else f"/{raw}"


router = APIRouter(prefix=_admin_panel_path(), tags=["admin"])


class GrantCreditBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    amount: int = Field(ge=1, le=100_000)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=120)
    payment_id: str | None = Field(default=None, max_length=80)


def _admin_email_set() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "")
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Not Found")


async def require_admin(
    request: Request,
    user_lookup: UserAdminLookupPort = Depends(get_user_admin_lookup_port),
) -> str:
    token = request.cookies.get("user_token")
    admin_emails = _admin_email_set()
    if token is None or SECRET_KEY is None or not admin_emails:
        raise _not_found()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload["user_id"]
    except (jwt.PyJWTError, KeyError):
        raise _not_found()

    if not isinstance(user_id, str):
        raise _not_found()

    user = await user_lookup.find_by_id(user_id)
    if user is None or not user.is_active or user.email is None:
        raise _not_found()

    if user.email.lower() not in admin_emails:
        raise _not_found()

    return user.user_id


def get_admin_ops_query(
    db: AsyncSession = Depends(get_async_db),
) -> SqlAlchemyAdminOpsQuery:
    return SqlAlchemyAdminOpsQuery(db)


def get_admin_ops_service(
    db: AsyncSession = Depends(get_async_db),
) -> AdminOpsService:
    return AdminOpsService(db, _get_toss_pay_gateway())


@router.get("/me")
async def admin_me(user_id: str = Depends(require_admin)):
    return {"ok": True, "user_id": user_id}


@router.get("/overview")
async def admin_overview(
    admin_user_id: str = Depends(require_admin),
    query: SqlAlchemyAdminOpsQuery = Depends(get_admin_ops_query),
):
    return await query.get_overview(admin_user_id)


@router.get("/support/credit-case")
async def get_credit_case(
    search_query: str = Query(alias="query", min_length=1, max_length=120),
    admin_user_id: str = Depends(require_admin),
    query: SqlAlchemyAdminOpsQuery = Depends(get_admin_ops_query),
):
    result = await query.get_credit_case(admin_user_id, search_query)
    if result is None:
        raise NotFoundException("사용자를 찾을 수 없습니다")
    return result


@router.post("/payments/{payment_id}/recheck")
async def recheck_payment(
    payment_id: str,
    admin_user_id: str = Depends(require_admin),
    service: AdminOpsService = Depends(get_admin_ops_service),
):
    return await service.recheck_payment(admin_user_id, payment_id)


@router.post("/credits/grant")
async def grant_credit(
    body: GrantCreditBody,
    admin_user_id: str = Depends(require_admin),
    service: AdminOpsService = Depends(get_admin_ops_service),
):
    reason = body.reason.strip()
    if not reason:
        raise BusinessRuleException("지급 사유가 필요합니다")
    return await service.grant_credit(
        admin_user_id=admin_user_id,
        user_id=body.user_id,
        amount=body.amount,
        reason=reason,
        idempotency_key=body.idempotency_key,
        payment_id=body.payment_id,
    )
