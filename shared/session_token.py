import os
from typing import Any

import jwt


def decode_session_token(token: str, secret_key: str | None) -> dict[str, Any]:
    payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    if (
        "review_login" in payload
        and payload["review_login"] is True
        and os.getenv("PG_REVIEW_LOGIN_ENABLED", "false").lower() != "true"
    ):
        raise jwt.InvalidTokenError("심사용 로그인이 비활성화되었습니다")
    return payload
