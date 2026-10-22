import asyncio
import os
import unittest
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TEST_URL = os.getenv("DAILY_REWARD_TEST_DATABASE_URL")
if not TEST_URL:
    raise unittest.SkipTest("Set DAILY_REWARD_TEST_DATABASE_URL to an empty disposable local database")
target = make_url(TEST_URL)
if target.get_backend_name() != "postgresql" or target.host != "127.0.0.1" or target.database != "gifgloo_daily_reward_verify":
    raise unittest.SkipTest("Only the explicitly named disposable local database is allowed")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["ASYNC_DATABASE_URL"] = target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)

from config.database import Base
from credit_account.adapter.outbound.models import CreditAccountModel, CreditLotModel, CreditTransactionModel
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import SqlAlchemyAsyncCreditAccountRepository
from credit_account.application.ports.inbound.daily_credit_reward import DailyCreditRewardCommand
from credit_account.application.services.daily_credit_reward_service import DailyCreditRewardService


class DailyRewardPostgresTest(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        engine = create_engine(TEST_URL)
        try:
            if inspect(engine).get_table_names():
                raise unittest.SkipTest("Use a new empty disposable database")
            Base.metadata.create_all(engine, tables=[CreditAccountModel.__table__, CreditLotModel.__table__, CreditTransactionModel.__table__])
        finally:
            engine.dispose()

    async def asyncSetUp(self):
        self.engine = create_async_engine(os.environ["ASYNC_DATABASE_URL"])
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.user_id = str(uuid.uuid4())
        self.command = DailyCreditRewardCommand(self.user_id, datetime.now(timezone.utc))
        async with self.sessions.begin() as db:
            db.add(CreditAccountModel(user_id=self.user_id, balance=0))

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_ten_concurrent_requests_grant_one_lot_and_one_charge(self):
        async def claim():
            async with self.sessions.begin() as db:
                return await DailyCreditRewardService(SqlAlchemyAsyncCreditAccountRepository(db)).claim(self.command)
        results = await asyncio.gather(*(claim() for _ in range(10)))
        self.assertEqual(sum(result.granted for result in results), 1)
        async with self.sessions() as db:
            account = await db.get(CreditAccountModel, self.user_id)
            lots = (await db.scalars(select(CreditLotModel).where(CreditLotModel.account_user_id == self.user_id))).all()
            transactions = (await db.scalars(select(CreditTransactionModel).where(CreditTransactionModel.account_user_id == self.user_id))).all()
            self.assertEqual(account.balance, 30)
            self.assertEqual(len(lots), 1)
            self.assertEqual(len(transactions), 1)

    async def test_rollback_leaves_no_claim_and_retry_can_grant(self):
        async with self.sessions() as db:
            await DailyCreditRewardService(SqlAlchemyAsyncCreditAccountRepository(db)).claim(self.command)
            await db.rollback()
        async with self.sessions.begin() as db:
            service = DailyCreditRewardService(SqlAlchemyAsyncCreditAccountRepository(db))
            self.assertFalse((await service.get_status(self.command)).claimed)
            self.assertTrue((await service.claim(self.command)).granted)
