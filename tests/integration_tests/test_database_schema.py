import os
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import inspect

import asset.adapter.outbound.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import user.adapter.outbound.persistence.models  # noqa: F401
from asset.adapter.outbound.models import AssetModel
from composition.adapter.outbound.persistence.models import CompositionJobModel
from config.database import Base, SessionLocal, engine
from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
from user.adapter.outbound.persistence.models import UserModel


class DatabaseSchemaIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ["DATABASE_URL"]
        if "gifgloo_test" not in database_url:
            raise RuntimeError("DATABASE_URL must point to gifgloo_test for integration tests")
        Base.metadata.create_all(bind=engine)

    def test_expected_tables_exist(self):
        tables = set(inspect(engine).get_table_names())

        self.assertTrue({
            "assets",
            "composition_jobs",
            "credit_accounts",
            "credit_transactions",
            "users",
        }.issubset(tables))

    def test_can_persist_core_records(self):
        now = datetime.now(timezone.utc)
        user_id = f"integration-user-{uuid4()}"
        asset_id = f"integration-asset-{uuid4()}"
        job_id = f"integration-job-{uuid4()}"
        transaction_id = f"integration-transaction-{uuid4()}"
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
                    balance=3,
                ),
                CreditTransactionModel(
                    id=transaction_id,
                    account_user_id=user_id,
                    amount=-1,
                    transaction_type="DEDUCT",
                    created_at=now,
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
            self.assertEqual(session.get(CreditAccountModel, user_id).balance, 3)
            self.assertEqual(session.get(AssetModel, asset_id).user_id, user_id)
            self.assertEqual(session.get(CompositionJobModel, job_id).spec["mode"], "integration")
        finally:
            session.rollback()
            session.query(CreditTransactionModel).filter(
                CreditTransactionModel.id == transaction_id,
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
