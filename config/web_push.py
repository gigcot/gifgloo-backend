import asyncio
import logging
import os
import base64
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid
from shared.exceptions import ValidationException

from composition.adapter.outbound.persistence.sqlalchemy_async_composition_repository import SqlAlchemyAsyncCompositionRepository
from composition.adapter.outbound.persistence.sqlalchemy_async_transaction import SqlAlchemyAsyncTransaction
from composition.adapter.outbound.persistence.sqlalchemy_completion_notification_repository import SqlAlchemyCompletionNotificationRepository
from composition.adapter.outbound.web_push_adapter import WebPushAdapter
from composition.application.services.completion_notification_service import CompletionNotificationService, DispatchCompletionNotificationsService
from config.database import AsyncSessionLocal, get_async_db

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebPushSettings:
    public_key: str
    private_key: str
    subject: str


def get_web_push_settings() -> WebPushSettings | None:
    if os.getenv("WEB_PUSH_ENABLED", "false").lower() != "true":
        return None
    settings = WebPushSettings(public_key=os.environ["WEB_PUSH_PUBLIC_KEY"],
        private_key=os.environ["WEB_PUSH_PRIVATE_KEY"], subject=os.environ["WEB_PUSH_SUBJECT"])
    vapid = Vapid.from_string(settings.private_key)
    public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    if base64.urlsafe_b64encode(public).decode().rstrip("=") != settings.public_key.rstrip("="):
        raise ValidationException("Web Push 공개키와 비공개키가 일치하지 않습니다")
    if not settings.subject.startswith(("mailto:", "https://")):
        raise ValidationException("WEB_PUSH_SUBJECT에 운영자 연락처가 필요합니다")
    return settings


def get_completion_notification_service(db: AsyncSession = Depends(get_async_db)) -> CompletionNotificationService:
    return CompletionNotificationService(SqlAlchemyAsyncCompositionRepository(db),
        SqlAlchemyCompletionNotificationRepository(db), SqlAlchemyAsyncTransaction(db))


async def dispatch_completion_notifications(settings: WebPushSettings) -> None:
    push = WebPushAdapter(settings.private_key, settings.subject)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                await DispatchCompletionNotificationsService(SqlAlchemyCompletionNotificationRepository(db), push).execute()
        except SQLAlchemyError as exc:
            logger.error("completion_push_database_error type=%s", type(exc).__name__)
        except Exception as exc:
            logger.error("completion_push_dispatch_error type=%s; claimed items retry after lease expiry", type(exc).__name__)
        await asyncio.sleep(5)
