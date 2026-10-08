import os

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

from config.database import AsyncSessionLocal
from shared.exceptions import AuthenticationException
from shared.session_token import decode_session_token
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import SqlAlchemyAsyncUserRepository
from user.application.services.verify_session_service import VerifySessionService


class UserSessionMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        path = scope["path"]
        if path.startswith(("/oauth/", "/assets/shared/")) or path == "/users/anonymous-session":
            return await self.app(scope, receive, send)
        request = Request(scope)
        token = request.cookies.get("user_token")
        if token is not None:
            try:
                payload = decode_session_token(token, os.environ["JWT_SECRET_KEY"])
                async with AsyncSessionLocal() as db:
                    session = await VerifySessionService(SqlAlchemyAsyncUserRepository(db)).execute(
                        payload["user_id"], payload["session_version"],
                    )
                if "user_kind" not in payload and session.user_kind != "member":
                    raise AuthenticationException("익명 사용자는 레거시 세션을 사용할 수 없습니다")
            except (jwt.InvalidTokenError, AuthenticationException):
                response = JSONResponse({"message": "세션이 만료되었거나 변경되었습니다"}, status_code=401)
                response.delete_cookie("user_token")
                return await response(scope, receive, send)
            if session.user_kind == "anonymous" and path.startswith(("/payments", "/admin")):
                return await JSONResponse({"message": "회원 로그인이 필요합니다"}, status_code=403)(scope, receive, send)
            if (
                session.user_kind == "anonymous" and session.consent_required
                and scope["method"] == "POST"
                and path in ("/compositions", "/compositions/uploads", "/compositions/from-upload")
            ):
                return await JSONResponse({"message": "합성 전 이용 안내를 확인해주세요", "error": "CONSENT_REQUIRED"}, status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)
