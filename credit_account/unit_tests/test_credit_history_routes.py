import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test",
)
os.environ.setdefault(
    "ASYNC_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

from config.credit import (  # noqa: E402
    get_credit_history_service,
    get_credit_lot_history_service,
)
from credit_account.adapter.inbound.fastapi.credit_account_router import (  # noqa: E402
    router,
)
from credit_account.domain.value_objects.credit_source_type import (  # noqa: E402
    CreditSourceType,
)
from credit_account.domain.value_objects.transaction_type import TransactionType  # noqa: E402


class FakeCreditLotHistoryService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        created_at = datetime(2026, 8, 24, 3, 0, tzinfo=timezone.utc)
        return SimpleNamespace(
            items=[
                SimpleNamespace(
                    lot_id="lot-1",
                    payment_id="payment-1",
                    granted_amount=50,
                    granted_uses=5,
                    remaining_amount=30,
                    remaining_uses=3,
                    expires_at=datetime(2026, 8, 31, 3, 0, tzinfo=timezone.utc),
                    expired=False,
                    created_at=created_at,
                    order_id="order-1",
                    payment_amount=6600,
                    currency="KRW",
                    purpose="COMPOSITION_PASS_PURCHASE",
                    payment_status="APPROVED",
                    approved_at=created_at,
                    canceled_at=None,
                )
            ],
            has_more=True,
            next_cursor_created_at=created_at,
            next_cursor_id="lot-1",
        )


class FakeCreditHistoryService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        created_at = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)
        return SimpleNamespace(
            transactions=[
                SimpleNamespace(
                    id="transaction-1",
                    transaction_type=TransactionType.DEDUCT,
                    amount=10,
                    source_type=CreditSourceType.COMPOSITION,
                    source_id="job-1",
                    credit_lot_id="lot-1",
                    reason=None,
                    balance_after=30,
                    created_at=created_at,
                )
            ],
            has_more=False,
            next_cursor_created_at=None,
            next_cursor_id=None,
        )


class CreditHistoryRoutesTest(unittest.TestCase):
    def setUp(self):
        self.lot_service = FakeCreditLotHistoryService()
        self.history_service = FakeCreditHistoryService()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[
            get_credit_lot_history_service
        ] = lambda: self.lot_service
        app.dependency_overrides[
            get_credit_history_service
        ] = lambda: self.history_service
        self.client = TestClient(app)
        token = jwt.encode(
            {"user_id": "user-1"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        self.client.cookies.set("user_token", token)

    def test_returns_paginated_payment_lots(self):
        response = self.client.get("/credits/lots?limit=10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["remaining_uses"], 3)
        self.assertEqual(response.json()["items"][0]["payment_amount"], 6600)
        self.assertIsInstance(response.json()["next_cursor"], str)
        self.assertEqual(self.lot_service.command.user_id, "user-1")
        self.assertEqual(self.lot_service.command.limit, 10)

    def test_returns_signed_credit_transaction(self):
        response = self.client.get("/credits/history")

        self.assertEqual(response.status_code, 200)
        transaction = response.json()["items"][0]
        self.assertEqual(transaction["signed_amount"], -10)
        self.assertEqual(transaction["uses"], 1)
        self.assertEqual(transaction["balance_after_uses"], 3)
        self.assertEqual(transaction["source_type"], "COMPOSITION")
        self.assertIsNone(response.json()["next_cursor"])


if __name__ == "__main__":
    unittest.main()
