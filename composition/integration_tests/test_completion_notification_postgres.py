"""Requires a fresh, disposable PostgreSQL database; never uses project .env."""

import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from sqlalchemy import create_engine, delete, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TEST_URL = os.getenv("PUSH_TEST_DATABASE_URL")
if not TEST_URL:
    raise unittest.SkipTest("Set PUSH_TEST_DATABASE_URL for disposable PostgreSQL tests")
target = make_url(TEST_URL)
if (
    target.get_backend_name() != "postgresql"
    or target.host != "127.0.0.1"
    or target.port != 55433
    or target.database != "gifgloo_push_verify"
    or target.username != "gifgloo_verify"
):
    raise unittest.SkipTest("Only the explicitly named disposable local database is allowed")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["ASYNC_DATABASE_URL"] = target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)

from alembic import command
from alembic.config import Config
from composition.adapter.outbound.persistence.models import CompositionJobModel, CompletionNotificationModel
from composition.adapter.outbound.persistence.sqlalchemy_async_composition_repository import SqlAlchemyAsyncCompositionRepository
from composition.adapter.outbound.persistence.sqlalchemy_async_transaction import SqlAlchemyAsyncTransaction
from composition.adapter.outbound.persistence.sqlalchemy_completion_notification_repository import SqlAlchemyCompletionNotificationRepository
from composition.application.services.completion_notification_service import CompletionNotificationService
from composition.domain.entities.completion_notification import CompletionNotification
from shared.exceptions import NotFoundException


class CompletionNotificationPostgresTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.sync_engine = create_engine(TEST_URL)
        if inspect(cls.sync_engine).get_table_names():
            cls.sync_engine.dispose()
            raise unittest.SkipTest("Database is not empty; use a fresh disposable container")
        config = Config("alembic.ini")
        command.upgrade(config, "202610050001")
        with cls.sync_engine.begin() as connection:
            connection.execute(text("""
                INSERT INTO composition_jobs (id, user_id, status, created_at)
                VALUES ('migration-existing-job', 'existing-user', 'COMPLETED', now())
            """))
        command.upgrade(config, "202610070001")
        cls.indexes = inspect(cls.sync_engine).get_indexes("composition_notifications")
        command.downgrade(config, "202610050001")
        cls.removed_on_downgrade = "composition_notifications" not in inspect(cls.sync_engine).get_table_names()
        command.upgrade(config, "202610070001")

    @classmethod
    def tearDownClass(cls):
        cls.sync_engine.dispose()

    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["ASYNC_DATABASE_URL"], poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.jobs = []

    async def asyncTearDown(self):
        async with self.sessions() as db:
            await db.execute(delete(CompositionJobModel).where(CompositionJobModel.id.in_(self.jobs)))
            await db.commit()
        await self.engine.dispose()

    async def seed(self, status="COMPLETED", **values):
        job_id = str(uuid.uuid4())
        self.jobs.append(job_id)
        endpoint = f"https://fcm.googleapis.com/fcm/send/{job_id}"
        item = CompletionNotification(job_id, "test-owner", endpoint, "test-public-key", "test-auth",
                                      sha256(endpoint.encode()).hexdigest(), **values)
        async with self.sessions() as db:
            db.add(CompositionJobModel(id=job_id, user_id=item.user_id, status=status, created_at=datetime.now(timezone.utc)))
            await db.flush()
            await SqlAlchemyCompletionNotificationRepository(db).register(item)
            await db.commit()
        return item

    async def claim(self, now):
        async with self.sessions() as db:
            return await SqlAlchemyCompletionNotificationRepository(db).claim_ready(now)

    async def test_migration_round_trip_preserves_jobs_and_adds_dispatch_index(self):
        self.assertTrue(self.removed_on_downgrade)
        self.assertIn("ix_composition_notifications_ready", {index["name"] for index in self.indexes})
        async with self.sessions() as db:
            self.assertEqual((await db.get(CompositionJobModel, "migration-existing-job")).status, "COMPLETED")
            self.assertEqual(await db.scalar(text("SELECT version_num FROM alembic_version")), "202610070001")

    async def test_eight_concurrent_registrations_keep_one_subscription(self):
        item = await self.seed(status="PROCESSING")
        async with self.sessions() as db:
            await db.execute(delete(CompletionNotificationModel).where(CompletionNotificationModel.id == item.id))
            await db.commit()

        async def register():
            async with self.sessions() as db:
                service = CompletionNotificationService(SqlAlchemyAsyncCompositionRepository(db),
                    SqlAlchemyCompletionNotificationRepository(db), SqlAlchemyAsyncTransaction(db))
                return await service.register(item.user_id, item.job_id, item.endpoint, item.p256dh, item.auth)

        self.assertEqual(await asyncio.gather(*(register() for _ in range(8))), ["pending"] * 8)
        async with self.sessions() as db:
            rows = (await db.scalars(select(CompletionNotificationModel).where(CompletionNotificationModel.job_id == item.job_id))).all()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].attempts, 0)

    async def test_eight_dispatchers_claim_one_job_once(self):
        item = await self.seed()
        results = await asyncio.gather(*(self.claim(datetime.now(timezone.utc)) for _ in range(8)))
        claims = [result for result in results if result is not None]
        self.assertEqual([result.id for result in claims], [item.id])
        self.assertEqual(claims[0].attempts, 1)

    async def test_locked_first_row_does_not_block_another_job(self):
        now = datetime.now(timezone.utc)
        first = await self.seed(created_at=now - timedelta(seconds=1))
        second = await self.seed(created_at=now)
        async with self.sessions() as lock_holder:
            await lock_holder.scalar(select(CompletionNotificationModel).where(
                CompletionNotificationModel.id == first.id).with_for_update())
            claimed = await asyncio.wait_for(self.claim(datetime.now(timezone.utc)), timeout=3)
            self.assertEqual(claimed.id, second.id)
            await lock_holder.rollback()
        self.assertEqual((await self.claim(datetime.now(timezone.utc))).id, first.id)

    async def test_new_session_recovers_expired_lease_and_rejects_stale_settle(self):
        item = await self.seed()
        now = datetime.now(timezone.utc)
        first = await self.claim(now)
        self.assertIsNone(await self.claim(now + timedelta(seconds=119)))
        second = await self.claim(now + timedelta(minutes=2))
        self.assertEqual((second.id, second.attempts), (item.id, 2))
        first.settle("accepted", now)
        async with self.sessions() as db:
            repo = SqlAlchemyCompletionNotificationRepository(db)
            await repo.settle(first)
            row = await db.get(CompletionNotificationModel, item.id)
            self.assertEqual((row.status, row.attempts), ("pending", 2))
            self.assertTrue(row.endpoint)
        second.settle("accepted", now + timedelta(minutes=2))
        async with self.sessions() as db:
            await SqlAlchemyCompletionNotificationRepository(db).settle(second)
            row = await db.get(CompletionNotificationModel, item.id)
            self.assertEqual((row.status, row.endpoint, row.p256dh, row.auth), ("sent", "", "", ""))
        self.assertIsNone(await self.claim(now + timedelta(minutes=5)))

    async def test_only_completed_unexpired_jobs_are_ready(self):
        pending = await self.seed(status="PROCESSING")
        await self.seed(status="FAILED")
        await self.seed(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertIsNone(await self.claim(datetime.now(timezone.utc)))
        async with self.sessions() as db:
            await db.execute(update(CompositionJobModel).where(CompositionJobModel.id == pending.job_id).values(status="COMPLETED"))
            await db.commit()
        self.assertEqual((await self.claim(datetime.now(timezone.utc))).id, pending.id)

    async def test_cancel_and_reregister_separates_delivery_generation(self):
        item = await self.seed()
        old = await self.claim(datetime.now(timezone.utc))
        async with self.sessions() as db:
            service = CompletionNotificationService(SqlAlchemyAsyncCompositionRepository(db),
                SqlAlchemyCompletionNotificationRepository(db), SqlAlchemyAsyncTransaction(db))
            await service.cancel(item.user_id, item.job_id, item.endpoint)
            await service.register(item.user_id, item.job_id, item.endpoint, item.p256dh, item.auth)
        current = await self.claim(datetime.now(timezone.utc))
        self.assertNotEqual(current.id, old.id)
        old.settle("accepted", datetime.now(timezone.utc))
        async with self.sessions() as db:
            await SqlAlchemyCompletionNotificationRepository(db).settle(old)
            row = await db.get(CompletionNotificationModel, current.id)
            self.assertEqual((row.status, row.attempts), ("pending", 1))
            self.assertTrue(row.endpoint)

    async def test_cancel_cannot_be_overwritten_by_inflight_success(self):
        item = await self.seed()
        claimed = await self.claim(datetime.now(timezone.utc))
        async with self.sessions() as db:
            repo = SqlAlchemyCompletionNotificationRepository(db)
            await repo.cancel(item.job_id, "wrong-owner", item.endpoint_hash)
            await db.commit()
            self.assertEqual((await db.get(CompletionNotificationModel, item.id)).status, "pending")
            await repo.cancel(item.job_id, item.user_id, item.endpoint_hash)
            await db.commit()
            claimed.settle("accepted", datetime.now(timezone.utc))
            await repo.settle(claimed)
            row = await db.get(CompletionNotificationModel, item.id)
            self.assertEqual((row.status, row.endpoint, row.p256dh, row.auth), ("cancelled", "", "", ""))

    async def test_cleanup_respects_active_lease_and_erases_exhausted_destinations(self):
        now = datetime.now(timezone.utc)
        expired = await self.seed(expires_at=now)
        exhausted = await self.seed(attempts=3, next_attempt_at=now)
        active = await self.seed(attempts=3, next_attempt_at=now + timedelta(minutes=2))
        async with self.sessions() as db:
            await SqlAlchemyCompletionNotificationRepository(db).clean_expired(now)
            self.assertIsNone(await db.get(CompletionNotificationModel, expired.id))
            row = await db.get(CompletionNotificationModel, exhausted.id)
            self.assertEqual((row.status, row.endpoint, row.p256dh, row.auth), ("failed", "", "", ""))
            row = await db.get(CompletionNotificationModel, active.id)
            self.assertEqual(row.status, "pending")
            self.assertTrue(row.endpoint)

    async def test_owner_gate_and_job_deletion_cascade(self):
        item = await self.seed()
        async with self.sessions() as db:
            service = CompletionNotificationService(SqlAlchemyAsyncCompositionRepository(db),
                SqlAlchemyCompletionNotificationRepository(db), SqlAlchemyAsyncTransaction(db))
            with self.assertRaises(NotFoundException):
                await service.register("wrong-owner", item.job_id, item.endpoint, item.p256dh, item.auth)
            await db.rollback()
            await db.execute(delete(CompositionJobModel).where(CompositionJobModel.id == item.job_id))
            await db.commit()
            self.assertIsNone(await db.get(CompletionNotificationModel, item.id))
