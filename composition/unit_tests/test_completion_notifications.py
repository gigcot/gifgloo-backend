import base64
import os
import unittest
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from unittest.mock import AsyncMock, Mock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from composition.adapter.inbound.fastapi.push_subscription import validate_push_subscription
from composition.adapter.outbound.persistence.models import CompositionJobModel, CompletionNotificationModel
from composition.adapter.outbound.persistence.sqlalchemy_completion_notification_repository import SqlAlchemyCompletionNotificationRepository
from composition.adapter.outbound.web_push_adapter import WebPushAdapter, NoRedirectSession
from composition.application.services.completion_notification_service import CompletionNotificationService, DispatchCompletionNotificationsService
from composition.application.ports.outbound.completion_push_port import CompletionPushCommand
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.entities.completion_notification import CompletionNotification
from shared.exceptions import NotFoundException, InvalidStateException, ValidationException


def notification(job_id="job"):
    endpoint = "https://fcm.googleapis.com/fcm/send/example"
    return CompletionNotification(job_id, "anonymous", endpoint, "test-public", "test-auth", sha256(endpoint.encode()).hexdigest())


class CompletionNotificationServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_owner_and_job_state_are_checked_without_user_kind_gate(self):
        job = CompositionJob("anonymous")
        jobs, repo, tx = AsyncMock(), AsyncMock(), AsyncMock()
        jobs.find_for_update.return_value = job
        repo.register.return_value = "pending"
        service = CompletionNotificationService(jobs, repo, tx)
        self.assertEqual(await service.register("anonymous", job.id, "endpoint", "key", "auth"), "pending")
        tx.commit.assert_awaited_once()
        with self.assertRaises(NotFoundException):
            await service.register("other-user", job.id, "endpoint", "key", "auth")
        job.fail("failed")
        with self.assertRaises(InvalidStateException):
            await service.register("anonymous", job.id, "endpoint", "key", "auth")
        jobs.find_for_update.return_value = None
        with self.assertRaises(NotFoundException):
            await service.register("anonymous", "missing", "endpoint", "key", "auth")

    async def test_dispatch_records_transient_failure_separately(self):
        item = notification()
        item.claim(datetime.now(timezone.utc))
        repo, push = AsyncMock(), AsyncMock()
        repo.claim_ready.side_effect = [item, None]
        push.send.return_value = "retry"
        self.assertEqual(await DispatchCompletionNotificationsService(repo, push).execute(), 1)
        self.assertEqual(item.status, "pending")
        self.assertTrue(item.endpoint)
        repo.settle.assert_awaited_once_with(item)

    def test_terminal_outcome_removes_sensitive_destination_and_bounds_retries(self):
        for outcome in ("accepted", "invalid", "retry"):
            item = notification()
            item.attempts = 3
            item.settle(outcome, datetime.now(timezone.utc))
            self.assertEqual(item.status, "sent" if outcome == "accepted" else "failed")
            self.assertEqual((item.endpoint, item.p256dh, item.auth), ("", "", ""))


class PushValidationTest(unittest.TestCase):
    def setUp(self):
        key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.key = base64.urlsafe_b64encode(key).decode().rstrip("=")
        self.auth = base64.urlsafe_b64encode(b"0" * 16).decode().rstrip("=")

    def test_valid_services_and_keys(self):
        for host in ("fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com", "wns2.notify.windows.com"):
            validate_push_subscription(f"https://{host}/some-endpoint", self.key, self.auth)

    def test_rejects_internal_http_credentials_ports_suffix_spoof_and_bad_keys(self):
        for endpoint in ("http://fcm.googleapis.com/x", "https://127.0.0.1/x", "https://169.254.169.254/x", "https://web.push.apple.com.evil.test/x", "https://evil@fcm.googleapis.com/x", "https://fcm.googleapis.com:8443/x", "https://fcm.googleapis.com/x#fragment"):
            with self.assertRaises(ValidationException):
                validate_push_subscription(endpoint, self.key, self.auth)
        with self.assertRaises(ValidationException):
            validate_push_subscription("https://fcm.googleapis.com/x", "bad-key", self.auth)

    def test_push_transport_disallows_redirects(self):
        with patch("requests.Session.post") as post:
            NoRedirectSession().post("https://fcm.googleapis.com/x", timeout=10)
            self.assertFalse(post.call_args.kwargs["allow_redirects"])


class PushAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_sends_only_private_result_route_with_finite_ttl(self):
        with patch("composition.adapter.outbound.web_push_adapter.webpush", return_value=Mock(status_code=201)) as send:
            result = await WebPushAdapter("test-key", "mailto:ops@example.test").send(CompletionPushCommand("https://fcm.googleapis.com/x", "k", "a", "job"))
            self.assertEqual(result, "accepted")
            self.assertIn("/my-assets?job=job", send.call_args.kwargs["data"])
            self.assertNotIn("result_url", send.call_args.kwargs["data"])
            self.assertEqual(send.call_args.kwargs["ttl"], 3600)


class NotificationPersistenceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite://")
        async with self.engine.begin() as connection:
            await connection.run_sync(lambda conn: CompositionJobModel.__table__.create(conn))
            await connection.run_sync(lambda conn: CompletionNotificationModel.__table__.create(conn))
        self.db = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.repo = SqlAlchemyCompletionNotificationRepository(self.db)
        self.job = CompositionJobModel(id="job", user_id="anonymous", status="PROCESSING", created_at=datetime.now(timezone.utc))
        self.db.add(self.job)
        await self.db.commit()

    async def asyncTearDown(self):
        await self.db.close()
        await self.engine.dispose()

    async def test_idempotent_registration_waits_for_completion_then_is_not_resent(self):
        await self.repo.register(notification())
        await self.db.commit()
        await self.repo.register(notification())
        await self.db.commit()
        self.assertEqual(len((await self.db.scalars(select(CompletionNotificationModel))).all()), 1)
        self.assertIsNone(await self.repo.claim_ready(datetime.now(timezone.utc)))
        self.job.status = "COMPLETED"
        await self.db.commit()
        item = await self.repo.claim_ready(datetime.now(timezone.utc))
        self.assertEqual(item.attempts, 1)
        self.assertIsNone(await self.repo.claim_ready(datetime.now(timezone.utc)))
        item.settle("accepted", datetime.now(timezone.utc))
        await self.repo.settle(item)
        self.assertIsNone(await self.repo.claim_ready(datetime.now(timezone.utc) + timedelta(minutes=3)))
        self.assertEqual(await self.repo.register(notification()), "sent")

    async def test_registration_after_completion_and_crash_lease_recovery(self):
        self.job.status = "COMPLETED"
        await self.db.commit()
        await self.repo.register(notification())
        await self.db.commit()
        now = datetime.now(timezone.utc)
        first = await self.repo.claim_ready(now)
        second = await self.repo.claim_ready(now + timedelta(minutes=3))
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.attempts, 2)

    async def test_reregistration_cannot_be_settled_by_a_cancelled_delivery(self):
        self.job.status = "COMPLETED"
        await self.db.commit()
        await self.repo.register(notification())
        await self.db.commit()
        old = await self.repo.claim_ready(datetime.now(timezone.utc))
        await self.repo.cancel(old.job_id, old.user_id, old.endpoint_hash)
        await self.db.commit()
        await self.repo.register(notification())
        await self.db.commit()
        current = await self.repo.claim_ready(datetime.now(timezone.utc))
        old.settle("accepted", datetime.now(timezone.utc))
        await self.repo.settle(old)
        row = await self.db.get(CompletionNotificationModel, current.id)
        self.assertEqual(row.status, "pending")
        self.assertNotEqual(current.id, old.id)

    async def test_cancel_ownership_and_expiration(self):
        item = notification()
        await self.repo.register(item)
        await self.db.commit()
        await self.repo.cancel("job", "someone-else", item.endpoint_hash)
        await self.db.commit()
        self.assertEqual((await self.db.get(CompletionNotificationModel, item.id)).status, "pending")
        await self.repo.cancel("job", "anonymous", item.endpoint_hash)
        await self.db.commit()
        self.assertEqual((await self.db.get(CompletionNotificationModel, item.id)).status, "cancelled")
        await self.repo.clean_expired(datetime.now(timezone.utc) + timedelta(hours=25))
        self.assertEqual((await self.db.scalars(select(CompletionNotificationModel))).all(), [])
