import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request

from admin.application.ports.outbound.domain_bridges.user_admin_lookup_port import (
    UserAdminLookupPort,
)
from config.admin import get_user_admin_lookup_port

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _admin_panel_path() -> str:
    raw = os.getenv("ADMIN_PANEL_PATH", "").strip()
    if not raw:
        return "/admin-disabled"
    return raw if raw.startswith("/") else f"/{raw}"


router = APIRouter(prefix=_admin_panel_path(), tags=["admin"])


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


@router.get("/me")
async def admin_me(user_id: str = Depends(require_admin)):
    return {"ok": True, "user_id": user_id}
