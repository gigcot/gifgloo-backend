from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.models import CompletionNotificationModel, CompositionJobModel
from composition.domain.entities.completion_notification import CompletionNotification


class SqlAlchemyCompletionNotificationRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def register(self, notification: CompletionNotification) -> str:
        existing = await self._db.scalar(select(CompletionNotificationModel).where(
            CompletionNotificationModel.job_id == notification.job_id,
            CompletionNotificationModel.endpoint_hash == notification.endpoint_hash,
        ))
        if existing is not None:
            if existing.status in ("failed", "cancelled"):
                for key, value in asdict(notification).items():
                    setattr(existing, key, value)
                return "pending"
            return existing.status
        self._db.add(CompletionNotificationModel(**asdict(notification)))
        await self._db.flush()
        return "pending"

    async def claim_ready(self, now: datetime) -> CompletionNotification | None:
        row = await self._db.scalar(select(CompletionNotificationModel).join(
            CompositionJobModel, CompositionJobModel.id == CompletionNotificationModel.job_id,
        ).where(
            CompletionNotificationModel.status == "pending",
            CompletionNotificationModel.next_attempt_at <= now,
            CompletionNotificationModel.expires_at > now,
            CompletionNotificationModel.attempts < 3,
            CompositionJobModel.status == "COMPLETED",
        ).order_by(CompletionNotificationModel.created_at).limit(1).with_for_update(
            skip_locked=True, of=CompletionNotificationModel,
        ))
        if row is None:
            await self._db.commit()
            return None
        notification = CompletionNotification(**{key: getattr(row, key) for key in CompletionNotification.__dataclass_fields__})
        notification.claim(now)
        row.attempts = notification.attempts
        row.next_attempt_at = notification.next_attempt_at
        await self._db.commit()
        return notification

    async def settle(self, notification: CompletionNotification) -> None:
        await self._db.execute(update(CompletionNotificationModel).where(
            CompletionNotificationModel.id == notification.id,
            CompletionNotificationModel.status == "pending",
            CompletionNotificationModel.attempts == notification.attempts,
        ).values(status=notification.status, next_attempt_at=notification.next_attempt_at,
                 endpoint=notification.endpoint, p256dh=notification.p256dh, auth=notification.auth))
        await self._db.commit()

    async def cancel(self, job_id: str, user_id: str, endpoint_hash: str) -> None:
        await self._db.execute(update(CompletionNotificationModel).where(
            CompletionNotificationModel.job_id == job_id,
            CompletionNotificationModel.user_id == user_id,
            CompletionNotificationModel.endpoint_hash == endpoint_hash,
            CompletionNotificationModel.status == "pending",
        ).values(status="cancelled", endpoint="", p256dh="", auth=""))

    async def clean_expired(self, now: datetime) -> None:
        await self._db.execute(update(CompletionNotificationModel).where(
            CompletionNotificationModel.status == "pending",
            CompletionNotificationModel.attempts >= 3,
            CompletionNotificationModel.next_attempt_at <= now,
        ).values(status="failed", endpoint="", p256dh="", auth=""))
        await self._db.execute(delete(CompletionNotificationModel).where(CompletionNotificationModel.expires_at <= now))
        await self._db.commit()
