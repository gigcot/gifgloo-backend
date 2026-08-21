import os
import unittest
from types import SimpleNamespace

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

from config.payment import (  # noqa: E402
    get_confirm_portone_payment_service,
    get_create_payment_order_service,
    get_handle_toss_pay_callback_service,
)
from payment.adapter.inbound.fastapi.payment_router import router  # noqa: E402
from payment.domain.value_objects.payment_status import PaymentStatus  # noqa: E402
from payment.domain.value_objects.payment_purpose import PaymentPurpose  # noqa: E402


class FakeCreatePaymentOrderService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        return SimpleNamespace(
            payment_id="payment-1",
            order_id="order-1",
            amount=6600,
            credit_amount=50,
            purpose=PaymentPurpose.COMPOSITION_PASS_PURCHASE,
            currency="KRW",
            status=PaymentStatus.READY,
            order_name="GIF 합성 5회 이용권",
        )


class FakeConfirmPortOnePaymentService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        return SimpleNamespace(
            payment_id="payment-1",
            status=PaymentStatus.APPROVED,
            already_processed=False,
            test_payment=True,
        )


class FakeHandleTossPayCallbackService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        return SimpleNamespace(
            payment_id="payment-1",
            status=PaymentStatus.APPROVED,
            already_processed=False,
        )


class PaymentRoutesTest(unittest.TestCase):
    def setUp(self):
        self.create_service = FakeCreatePaymentOrderService()
        self.confirm_service = FakeConfirmPortOnePaymentService()
        self.callback_service = FakeHandleTossPayCallbackService()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[
            get_create_payment_order_service
        ] = lambda: self.create_service
        app.dependency_overrides[
            get_handle_toss_pay_callback_service
        ] = lambda: self.callback_service
        app.dependency_overrides[
            get_confirm_portone_payment_service
        ] = lambda: self.confirm_service
        self.client = TestClient(app)

    def _set_auth_cookie(self):
        token = jwt.encode(
            {"user_id": "user-1"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        self.client.cookies.set("user_token", token)

    def test_checkout_accepts_only_product_selection(self):
        self._set_auth_cookie()

        response = self.client.post(
            "/payments/checkout",
            json={
                "product_id": "composition_pass_5_7d",
                "amount": 1,
                "credit_amount": 999999,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["amount"], 6600)
        self.assertEqual(response.json()["credit_amount"], 50)
        self.assertEqual(self.create_service.command.user_id, "user-1")
        self.assertEqual(self.create_service.command.product_id, "composition_pass_5_7d")
        self.assertEqual(response.json()["order_name"], "GIF 합성 5회 이용권")

    def test_products_exposes_only_five_use_pass(self):
        response = self.client.get("/payments/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [product["id"] for product in response.json()],
            ["composition_pass_5_7d"],
        )
        self.assertEqual(response.json()[0]["usage_count"], 5)
        self.assertEqual(response.json()[0]["validity_days"], 7)

    def test_completes_portone_payment_for_authenticated_user(self):
        self._set_auth_cookie()

        response = self.client.post(
            "/payments/complete",
            json={"payment_id": "gifgloo_0123456789abcdef0123456789abcdef"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["test_payment"])
        self.assertEqual(self.confirm_service.command.expected_user_id, "user-1")

    def test_maps_paid_portone_webhook(self):
        response = self.client.post(
            "/payments/portone/webhook",
            json={
                "type": "Transaction.Paid",
                "data": {
                    "paymentId": "gifgloo_0123456789abcdef0123456789abcdef"
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.confirm_service.command.expected_user_id)

    def test_ignores_non_paid_portone_webhook(self):
        response = self.client.post(
            "/payments/portone/webhook",
            json={
                "type": "Transaction.Failed",
                "data": {
                    "paymentId": "gifgloo_0123456789abcdef0123456789abcdef"
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ignored"])
        self.assertIsNone(self.confirm_service.command)

    def test_callback_maps_toss_v2_payload(self):
        order_id = "gifgloo_0123456789abcdef0123456789abcdef"
        response = self.client.post(
            "/payments/toss/callback",
            json={
                "status": "PAY_COMPLETE",
                "payToken": "pay-token-1",
                "orderNo": order_id,
                "payMethod": "CARD",
                "amount": 6600,
                "discountedAmount": 0,
                "paidAmount": 6600,
                "paidTs": "2026-08-05 12:00:00",
                "transactionId": "transaction-1",
                "cardNumber": "123456******7890",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(self.callback_service.command.order_id, order_id)
        self.assertNotIn("cardNumber", self.callback_service.command.payload)
