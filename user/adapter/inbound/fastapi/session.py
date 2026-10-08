import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.responses import Response

BOOTSTRAP_COOKIE = "anonymous_bootstrap"


def session_seconds() -> int:
    return int(os.getenv("USER_SESSION_DAYS", "180")) * 24 * 60 * 60


def issue_session_token(user_id: str, user_kind: str, session_version: int, review_login: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id, "user_kind": user_kind, "session_version": session_version,
        "purpose": "user_session", "iat": now, "exp": now + timedelta(seconds=session_seconds()),
    }
    if review_login:
        payload["review_login"] = True
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm="HS256")


def set_user_cookie(response: Response, user_id: str, user_kind: str, session_version: int, review_login: bool = False) -> None:
    response.set_cookie(
        "user_token", issue_session_token(user_id, user_kind, session_version, review_login),
        httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE", "true").lower() == "true",
        max_age=session_seconds(),
    )
