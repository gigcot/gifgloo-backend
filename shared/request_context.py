from contextvars import ContextVar
import logging
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


current_request_path: ContextVar[str] = ContextVar(
    "current_request_path",
    default="unknown",
)

current_request_id: ContextVar[str] = ContextVar(
    "current_request_id",
    default="unknown",
)

logger = logging.getLogger(__name__)


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming_request_id = Headers(scope=scope).get("x-request-id")
        request_id = (
            incoming_request_id
            if incoming_request_id and len(incoming_request_id) <= 128
            else uuid.uuid4().hex
        )
        token = current_request_id.set(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
                status = message["status"]
                if status >= 500:
                    logger.error(
                        "HTTP response request_id=%s method=%s path=%s status=%s",
                        request_id,
                        scope["method"],
                        scope["path"],
                        status,
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            current_request_id.reset(token)
