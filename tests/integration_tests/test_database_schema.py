import os
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import inspect

import asset.adapter.outbound.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import payment.adapter.outbound.persistence.models  # noqa: F401
import user.adapter.outbound.persistence.models  # noqa: F401
from asset.adapter.outbound.models import AssetModel
from composition.adapter.outbound.persistence.models import CompositionJobModel
from config.database import SessionLocal, engine
from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
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

    def test_can_persist_core_records(self):
        now = datetime.now(timezone.utc)
        user_id = f"integration-user-{uuid4()}"
        asset_id = f"integration-asset-{uuid4()}"
        job_id = f"integration-job-{uuid4()}"
        transaction_id = f"integration-transaction-{uuid4()}"
        payment_id = f"integration-payment-{uuid4()}"
        order_id = f"integration-order-{uuid4()}"
        event_id = f"integration-event-{uuid4()}"
        session = SessionLocal()

        try:
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
                    balance=100,
                ),
                CreditTransactionModel(
                    id=transaction_id,
                    account_user_id=user_id,
                    amount=100,
                    transaction_type="CHARGE",
                    source_type="PAYMENT",
                    source_id=payment_id,
                    created_at=now,
                ),
                PaymentModel(
                    id=payment_id,
                    user_id=user_id,
                    provider="TOSS_PAY",
                    order_id=order_id,
                    amount=5000,
                    currency="KRW",
                    credit_amount=100,
                    provider_payment_id=payment_id,
                    provider_transaction_id=payment_id,
                    status="APPROVED",
                    created_at=now,
                    updated_at=now,
                    approved_at=now,
                    credit_granted_at=now,
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
            self.assertEqual(session.get(CreditAccountModel, user_id).balance, 100)
            self.assertEqual(
                session.get(CreditTransactionModel, transaction_id).source_id,
                payment_id,
            )
            self.assertEqual(session.get(PaymentModel, payment_id).credit_amount, 100)
            self.assertEqual(session.get(PaymentInboxModel, event_id).status, "PROCESSED")
            self.assertEqual(session.get(AssetModel, asset_id).user_id, user_id)
            self.assertEqual(session.get(CompositionJobModel, job_id).spec["mode"], "integration")
        finally:
            session.rollback()
            session.query(CreditTransactionModel).filter(
                CreditTransactionModel.id == transaction_id,
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
