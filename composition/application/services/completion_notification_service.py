from datetime import datetime, timezone
from hashlib import sha256

from composition.application.ports.outbound.completion_push_port import CompletionPushCommand, CompletionPushPort
from composition.application.ports.outbound.persistence.async_composition_repository import AsyncCompositionRepository
from composition.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from composition.application.ports.outbound.persistence.completion_notification_repository import CompletionNotificationRepository
from composition.domain.entities.completion_notification import CompletionNotification
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import NotFoundException, InvalidStateException


class CompletionNotificationService:
    def __init__(self, jobs: AsyncCompositionRepository, notifications: CompletionNotificationRepository, transaction: AsyncTransaction):
        self._jobs = jobs
        self._notifications = notifications
        self._transaction = transaction

    async def register(self, user_id: str, job_id: str, endpoint: str, p256dh: str, auth: str) -> str:
        job = await self._jobs.find_for_update(job_id)
        if job is None or job.user_id != user_id:
            raise NotFoundException("합성 작업을 찾을 수 없습니다")
        if job.status == CompositionStatus.FAILED:
            raise InvalidStateException("종료된 작업에는 알림을 신청할 수 없습니다")
        notification = CompletionNotification(job_id=job_id, user_id=user_id, endpoint=endpoint,
            p256dh=p256dh, auth=auth, endpoint_hash=sha256(endpoint.encode()).hexdigest())
        state = await self._notifications.register(notification)
        await self._transaction.commit()
        return state

    async def cancel(self, user_id: str, job_id: str, endpoint: str) -> None:
        await self._notifications.cancel(job_id, user_id, sha256(endpoint.encode()).hexdigest())
        await self._transaction.commit()


class DispatchCompletionNotificationsService:
    def __init__(self, notifications: CompletionNotificationRepository, push: CompletionPushPort):
        self._notifications = notifications
        self._push = push

    async def execute(self) -> int:
        await self._notifications.clean_expired(datetime.now(timezone.utc))
        count = 0
        for _ in range(20):
            notification = await self._notifications.claim_ready(datetime.now(timezone.utc))
            if notification is None:
                break
            outcome = await self._push.send(CompletionPushCommand(
                endpoint=notification.endpoint, p256dh=notification.p256dh,
                auth=notification.auth, job_id=notification.job_id,
            ))
            notification.settle(outcome, datetime.now(timezone.utc))
            await self._notifications.settle(notification)
            count += 1
        return count
