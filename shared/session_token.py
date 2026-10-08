import os
from typing import Any

import jwt


def decode_session_token(token: str, secret_key: str | None) -> dict[str, Any]:
    payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    if "purpose" in payload and payload["purpose"] != "user_session":
        raise jwt.InvalidTokenError("사용자 세션 토큰이 아닙니다")
    if "user_id" not in payload or not isinstance(payload["user_id"], str) or not payload["user_id"]:
        raise jwt.InvalidTokenError("사용자 식별이 없습니다")
    version = payload["session_version"] if "session_version" in payload else 0
    if type(version) is not int or version < 0:
        raise jwt.InvalidTokenError("세션 버전이 올바르지 않습니다")
    payload["session_version"] = version
    if (
        "review_login" in payload
        and payload["review_login"] is True
        and os.getenv("PG_REVIEW_LOGIN_ENABLED", "false").lower() != "true"
    ):
        raise jwt.InvalidTokenError("심사용 로그인이 비활성화되었습니다")
    return payload
