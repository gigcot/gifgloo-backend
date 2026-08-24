import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import inspect

import asset.adapter.outbound.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import payment.adapter.outbound.persistence.models  # noqa: F401
import user.adapter.outbound.persistence.models  # noqa: F401
from asset.adapter.outbound.models import AssetModel
from composition.adapter.outbound.persistence.models import CompositionJobModel
from config.database import AsyncSessionLocal, SessionLocal, engine
from credit_account.adapter.outbound.models import (
    CreditAccountModel,
    CreditLotModel,
    CreditTransactionModel,
)
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import (
    SqlAlchemyAsyncCreditAccountRepository,
)
from payment.adapter.outbound.persistence.models import PaymentInboxModel, PaymentModel
from user.adapter.outbound.persistence.models import UserModel


class DatabaseSchemaIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ["DATABASE_URL"]
        if "gifgloo_test" not in database_url:
            raise RuntimeError("DATABASE_URL must point to gifgloo_test for integration tests")

    def test_expected_tables_exist(self):
        tables = set(inspect(engine).get_table_names())

        self.assertTrue({
            "assets",
            "composition_jobs",
            "credit_accounts",
            "credit_lots",
            "credit_transactions",
            "payment_inbox",
            "payments",
            "users",
        }.issubset(tables))

    def test_payment_provider_id_is_unique_per_provider(self):
        unique_constraints = inspect(engine).get_unique_constraints("payments")
        provider_payment_constraint = next(
            constraint
            for constraint in unique_constraints
            if constraint["name"] == "uq_payments_provider_payment_id_by_provider"
        )

        self.assertEqual(
            provider_payment_constraint["column_names"],
            ["provider", "provider_payment_id"],
        )

    def test_payment_environment_is_required(self):
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns("payments")
        }

        self.assertIn("payment_environment", columns)
        self.assertFalse(columns["payment_environment"]["nullable"])

    def test_credit_history_indexes_exist(self):
        lot_indexes = {
            index["name"] for index in inspect(engine).get_indexes("credit_lots")
        }
        transaction_indexes = {
            index["name"]
            for index in inspect(engine).get_indexes("credit_transactions")
        }

        self.assertIn("ix_credit_lots_user_payment_history", lot_indexes)
        self.assertIn("ix_credit_transactions_user_history", transaction_indexes)

    def test_available_credit_summary_excludes_expired_and_empty_lots(self):
        observed_at = datetime.now(timezone.utc)
        user_id = f"integration-credit-summary-user-{uuid4()}"
        active_lot_id = f"integration-active-lot-{uuid4()}"
        expired_lot_id = f"integration-expired-lot-{uuid4()}"
        empty_lot_id = f"integration-empty-lot-{uuid4()}"
        session = SessionLocal()

        try:
            session.add(
                UserModel(
                    id=user_id,
                    provider="test",
                    provider_id=user_id,
                    email=f"{user_id}@example.com",
                    role="USER",
                    status="ACTIVE",
                    created_at=observed_at,
                )
            )
            session.add(
                CreditAccountModel(
                    user_id=user_id,
                    balance=70,
                )
            )
            session.add_all([
                CreditLotModel(
                    id=active_lot_id,
                    account_user_id=user_id,
                    granted_amount=30,
                    remaining_amount=30,
                    expires_at=observed_at + timedelta(days=7),
                    created_at=observed_at,
                ),
                CreditLotModel(
                    id=expired_lot_id,
                    account_user_id=user_id,
                    granted_amount=40,
                    remaining_amount=40,
                    expires_at=observed_at,
                    created_at=observed_at,
                ),
                CreditLotModel(
                    id=empty_lot_id,
                    account_user_id=user_id,
                    granted_amount=20,
                    remaining_amount=0,
                    expires_at=observed_at + timedelta(days=1),
                    created_at=observed_at,
                ),
            ])
            session.commit()

            summary = asyncio.run(
                self._find_available_credit_summary(user_id, observed_at)
            )

            self.assertIsNotNone(summary)
            self.assertEqual(summary.balance, 30)
            self.assertEqual(
                summary.nearest_expires_at,
                observed_at + timedelta(days=7),
            )
        finally:
            session.rollback()
            session.query(CreditLotModel).filter(
                CreditLotModel.account_user_id == user_id,
            ).delete(synchronize_session=False)
            session.query(CreditAccountModel).filter(
                CreditAccountModel.user_id == user_id,
            ).delete(synchronize_session=False)
            session.query(UserModel).filter(
                UserModel.id == user_id,
            ).delete(synchronize_session=False)
            session.commit()
            session.close()

    @staticmethod
    async def _find_available_credit_summary(user_id, observed_at):
        async with AsyncSessionLocal() as session:
            repository = SqlAlchemyAsyncCreditAccountRepository(session)
            return await repository.find_available_summary_by_user_id(
                user_id,
                observed_at,
            )

    def test_can_persist_core_records(self):
        now = datetime.now(timezone.utc)
        user_id = f"integration-user-{uuid4()}"
        asset_id = f"integration-asset-{uuid4()}"
        job_id = f"integration-job-{uuid4()}"
        transaction_id = f"integration-transaction-{uuid4()}"
        lot_id = f"integration-lot-{uuid4()}"
        payment_id = f"integration-payment-{uuid4()}"
        order_id = f"integration-order-{uuid4()}"
        event_id = f"integration-event-{uuid4()}"
        session = SessionLocal()

        try:
            session.add(
                PaymentModel(
                    id=payment_id,
                    user_id=user_id,
                    provider="TOSS_PAY",
                    order_id=order_id,
                    amount=6600,
                    currency="KRW",
                    credit_amount=50,
                    purpose="COMPOSITION_PASS_PURCHASE",
                    payment_environment="LIVE",
                    provider_payment_id=payment_id,
                    provider_transaction_id=payment_id,
                    status="APPROVED",
                    created_at=now,
                    updated_at=now,
                    approved_at=now,
                    credit_granted_at=now,
                )
            )
            session.flush()

            session.add_all([
                UserModel(
                    id=user_id,
                    provider="test",
                    provider_id=user_id,
                    email="integration@example.com",
                    role="USER",
                    status="ACTIVE",
                    created_at=now,
                ),
                CreditAccountModel(
                    user_id=user_id,
                    balance=50,
                ),
                CreditLotModel(
                    id=lot_id,
                    account_user_id=user_id,
                    source_type="PAYMENT",
                    source_id=payment_id,
                    granted_amount=50,
                    remaining_amount=50,
                    expires_at=now,
                    created_at=now,
                ),
                CreditTransactionModel(
                    id=transaction_id,
                    account_user_id=user_id,
                    amount=50,
                    transaction_type="CHARGE",
                    source_type="PAYMENT",
                    source_id=payment_id,
                    credit_lot_id=lot_id,
                    balance_after=50,
                    created_at=now,
                ),
                PaymentInboxModel(
                    id=event_id,
                    provider="TOSS_PAY",
                    external_event_id=event_id,
                    event_type="PAYMENT_APPROVED",
                    order_id=order_id,
                    payment_id=payment_id,
                    payload={"status": "APPROVED"},
                    status="PROCESSED",
                    attempts=1,
                    received_at=now,
                    processed_at=now,
                ),
                AssetModel(
                    id=asset_id,
                    user_id=user_id,
                    asset_type="IMAGE",
                    category="TARGET",
                    storage_url="https://assets.example/target.png",
                    status="READY",
                ),
                CompositionJobModel(
                    id=job_id,
                    user_id=user_id,
                    status="PROCESSING",
                    stage="ANALYZING",
                    gif_url="https://assets.example/source.gif",
                    source_gif_url="https://assets.example/source.gif",
                    target_url="https://assets.example/target.png",
                    target_asset_id=asset_id,
                    durations_ms=[100, 100],
                    spec={"mode": "integration"},
                    created_at=now,
                ),
            ])
            session.commit()

            self.assertEqual(session.get(UserModel, user_id).email, "integration@example.com")
            self.assertEqual(session.get(CreditAccountModel, user_id).balance, 50)
            self.assertEqual(
                session.get(CreditTransactionModel, transaction_id).source_id,
                payment_id,
            )
            self.assertEqual(session.get(PaymentModel, payment_id).credit_amount, 50)
            self.assertEqual(
                session.get(PaymentModel, payment_id).payment_environment,
                "LIVE",
            )
            self.assertEqual(session.get(PaymentInboxModel, event_id).status, "PROCESSED")
            self.assertEqual(session.get(AssetModel, asset_id).user_id, user_id)
            self.assertEqual(session.get(CompositionJobModel, job_id).spec["mode"], "integration")
        finally:
            session.rollback()
            session.query(CreditTransactionModel).filter(
                CreditTransactionModel.id == transaction_id,
            ).delete(synchronize_session=False)
            session.query(CreditLotModel).filter(
                CreditLotModel.id == lot_id,
            ).delete(synchronize_session=False)
            session.query(PaymentInboxModel).filter(
                PaymentInboxModel.id == event_id,
            ).delete(synchronize_session=False)
            session.query(PaymentModel).filter(
                PaymentModel.id == payment_id,
            ).delete(synchronize_session=False)
            session.query(CompositionJobModel).filter(
                CompositionJobModel.id == job_id,
            ).delete(synchronize_session=False)
            session.query(AssetModel).filter(
                AssetModel.id == asset_id,
            ).delete(synchronize_session=False)
            session.query(CreditAccountModel).filter(
                CreditAccountModel.user_id == user_id,
            ).delete(synchronize_session=False)
            session.query(UserModel).filter(
                UserModel.id == user_id,
            ).delete(synchronize_session=False)
            session.commit()
            session.close()
