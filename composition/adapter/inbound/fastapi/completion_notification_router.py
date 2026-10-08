import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from shared.fastapi_session import require_session_user_id
from composition.adapter.inbound.fastapi.push_subscription import validate_push_subscription
from composition.application.services.completion_notification_service import CompletionNotificationService
from config.web_push import get_web_push_settings, get_completion_notification_service

router = APIRouter(tags=["composition"])


class PushKeysCommand(BaseModel):
    p256dh: str = Field(min_length=80, max_length=128)
    auth: str = Field(min_length=20, max_length=64)


class PushSubscriptionCommand(BaseModel):
    endpoint: str = Field(min_length=10, max_length=4096)
    keys: PushKeysCommand


class CancelNotificationCommand(BaseModel):
    endpoint: str = Field(min_length=10, max_length=4096)


def require_push_origin(request: Request) -> None:
    if request.headers.get("origin") not in os.environ["CORS_ORIGINS"].split(","):
        raise HTTPException(403, "허용되지 않은 요청 출처입니다")


@router.get("/web-push/config")
def push_config(response: Response):
    response.headers["Cache-Control"] = "no-store"
    settings = get_web_push_settings()
    return {"enabled": settings is not None, "public_key": settings.public_key if settings else None}


@router.post("/compositions/{job_id}/notification")
async def subscribe(job_id: str, body: PushSubscriptionCommand, request: Request,
                    service: CompletionNotificationService = Depends(get_completion_notification_service)):
    require_push_origin(request)
    if get_web_push_settings() is None:
        raise HTTPException(503, "완료 알림을 아직 사용할 수 없습니다")
    validate_push_subscription(body.endpoint, body.keys.p256dh, body.keys.auth)
    status = await service.register(require_session_user_id(request), job_id, body.endpoint, body.keys.p256dh, body.keys.auth)
    return {"status": status}


@router.delete("/compositions/{job_id}/notification", status_code=204)
async def cancel(job_id: str, body: CancelNotificationCommand, request: Request,
                 service: CompletionNotificationService = Depends(get_completion_notification_service)):
    require_push_origin(request)
    await service.cancel(require_session_user_id(request), job_id, body.endpoint)
    return Response(status_code=204)
