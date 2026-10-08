import os

import jwt
from fastapi import HTTPException, Request

from shared.session_token import decode_session_token


def require_session_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if not token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        return decode_session_token(token, os.environ["JWT_SECRET_KEY"])["user_id"]
    except jwt.InvalidTokenError as exc:
        raise HTTPException(401, "유효하지 않은 토큰입니다") from exc
