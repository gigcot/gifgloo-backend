import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from config.payment_settings import required_portone_environment
from payment.adapter.outbound.payment_gateway.portone_http_adapter import (
    PortOneHttpAdapter,
)
from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentCommand,
)
from payment.application.ports.inbound.confirm_portone_payment import (
    ConfirmPortOnePaymentCommand,
)
from payment.application.ports.outbound.payment_gateway.portone_gateway import (
    GetPortOnePaymentCommand,
    GetPortOnePaymentResult,
)
from payment.application.ports.outbound.domain_bridges.credit_grant_port import (
    GrantPaymentCreditResult,
)
from payment.application.ports.outbound.inbox.payment_inbox_port import (
    AcquirePaymentInboxResult,
)
from payment.application.services.process_verified_payment_service import (
    ProcessVerifiedPaymentService,
)
from payment.application.services.confirm_portone_payment_service import (
    ConfirmPortOnePaymentService,
)
from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_environment import PaymentEnvironment
from payment.domain.value_objects.payment_status import PaymentStatus
from payment.domain.value_objects.payment_purpose import PaymentPurpose
from shared.exceptions import (
    BusinessRuleException,
    ExternalServiceException,
)


class FakePaymentRepository:
    def __init__(self, payment: Payment):
        self.payment = payment
        self.update_count = 0

    async def add(self, payment: Payment) -> None:
        self.payment = payment

    async def update(self, payment: Payment) -> None:
        self.payment = payment
        self.update_count += 1

    async def find_by_order_id(self, order_id: str) -> Payment | None:
        return self.payment if self.payment.order_id == order_id else None

    async def find_by_order_id_for_update(self, order_id: str) -> Payment | None:
        return self.payment if self.payment.order_id == order_id else None

    async def find_by_id(self, payment_id: str) -> Payment | None:
        return self.payment if self.payment.id == payment_id else None

    async def find_all_by_user_id(self, user_id: str) -> list[Payment]:
        return [self.payment] if self.payment.user_id == user_id else []


class FakePaymentInbox:
    def __init__(self):
        self.messages: dict[tuple[PaymentProvider, str], dict] = {}

    async def acquire(self, command):
        key = (command.provider, command.external_event_id)
        message = self.messages.get(key)
        if message is None:
            self.messages[key] = {
                "status": "RECEIVED",
                "payment_id": None,
            }
            return AcquirePaymentInboxResult(False, None)
        return AcquirePaymentInboxResult(
            already_processed=message["status"] == "PROCESSED",
            payment_id=message["payment_id"],
        )

    async def mark_processed(self, provider, external_event_id, payment_id):
        self.messages[(provider, external_event_id)] = {
            "status": "PROCESSED",
            "payment_id": payment_id,
        }


class FakeCreditGrant:
    def __init__(self):
        self.payment_ids: set[str] = set()
        self.call_count = 0

    async def grant(self, command):
        self.call_count += 1
        granted = command.payment_id not in self.payment_ids
        self.payment_ids.add(command.payment_id)
        return GrantPaymentCreditResult(granted=granted)


class FakeTransaction:
    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class ProcessVerifiedPaymentServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.payment = Payment(
            user_id="user-1",
            provider=PaymentProvider.TOSS_PAY,
            amount=5000,
            credit_amount=100,
            order_id="order-1",
        )
        self.payment_repo = FakePaymentRepository(self.payment)
        self.inbox = FakePaymentInbox()
        self.credit = FakeCreditGrant()
        self.transaction = FakeTransaction()
        self.service = ProcessVerifiedPaymentService(
            payment_repo=self.payment_repo,
            inbox=self.inbox,
            credit=self.credit,
            transaction=self.transaction,
        )

    def command(self, amount: int = 5000) -> ProcessVerifiedPaymentCommand:
        return ProcessVerifiedPaymentCommand(
            provider=PaymentProvider.TOSS_PAY,
            external_event_id="event-1",
            event_type="PAYMENT_APPROVED",
            order_id="order-1",
            provider_payment_id="provider-payment-1",
            provider_transaction_id="provider-transaction-1",
            amount=amount,
            currency="KRW",
            approved_at=datetime.now(timezone.utc),
            payment_environment=PaymentEnvironment.LIVE,
            payload={"status": "APPROVED"},
        )

    async def test_approves_payment_and_grants_credit_in_one_commit(self):
        result = await self.service.execute(self.command())

        self.assertEqual(result.status, PaymentStatus.APPROVED)
        self.assertFalse(result.already_processed)
        self.assertEqual(self.payment.status, PaymentStatus.APPROVED)
        self.assertIsNotNone(self.payment.credit_granted_at)
        self.assertEqual(
            self.payment.payment_environment,
            PaymentEnvironment.LIVE,
        )
        self.assertEqual(self.credit.call_count, 1)
        self.assertEqual(self.payment_repo.update_count, 1)
        self.assertEqual(self.transaction.commit_count, 1)
        self.assertEqual(self.transaction.rollback_count, 0)

    async def test_duplicate_event_does_not_grant_credit_twice(self):
        await self.service.execute(self.command())
        result = await self.service.execute(self.command())

        self.assertTrue(result.already_processed)
        self.assertEqual(self.credit.call_count, 1)
        self.assertEqual(self.transaction.commit_count, 2)
        self.assertEqual(self.transaction.rollback_count, 0)

    async def test_amount_mismatch_rolls_back_without_granting_credit(self):
        with self.assertRaises(BusinessRuleException):
            await self.service.execute(self.command(amount=6000))

        self.assertEqual(self.payment.status, PaymentStatus.READY)
        self.assertEqual(self.credit.call_count, 0)
        self.assertEqual(self.payment_repo.update_count, 0)
        self.assertEqual(self.transaction.commit_count, 0)
        self.assertEqual(self.transaction.rollback_count, 1)


class FakePortOneGateway:
    def __init__(self, result: GetPortOnePaymentResult):
        self.result = result
        self.command = None

    async def get_payment(self, command):
        self.command = command
        return self.result


class ConfirmPortOnePaymentServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.payment = Payment(
            user_id="user-1",
            provider=PaymentProvider.KG_INICIS,
            amount=6600,
            credit_amount=50,
            purpose=PaymentPurpose.COMPOSITION_PASS_PURCHASE,
            order_id="gifgloo_order_1",
        )
        self.payment_repo = FakePaymentRepository(self.payment)
        self.inbox = FakePaymentInbox()
        self.credit = FakeCreditGrant()
        self.transaction = FakeTransaction()
        self.process_payment = ProcessVerifiedPaymentService(
            payment_repo=self.payment_repo,
            inbox=self.inbox,
            credit=self.credit,
            transaction=self.transaction,
        )

    def _verified(self, **overrides):
        values = {
            "payment_id": self.payment.order_id,
            "transaction_id": "portone-transaction-1",
            "status": "PAID",
            "amount": 6600,
            "currency": "KRW",
            "paid_at": datetime.now(timezone.utc),
            "pg_provider": "HTML5_INICIS",
            "payment_environment": PaymentEnvironment.LIVE,
        }
        values.update(overrides)
        return GetPortOnePaymentResult(**values)

    def _service(
        self,
        verified,
        expected_environment=PaymentEnvironment.LIVE,
    ):
        return ConfirmPortOnePaymentService(
            portone_gateway=FakePortOneGateway(verified),
            process_payment=self.process_payment,
            payment_repo=self.payment_repo,
            expected_environment=expected_environment,
        )

    def _command(self):
        return ConfirmPortOnePaymentCommand(
            payment_id=self.payment.order_id,
            expected_user_id="user-1",
        )

    async def test_verifies_live_inicis_payment_and_grants_credit(self):
        result = await self._service(self._verified()).execute(self._command())

        self.assertEqual(result.status, PaymentStatus.APPROVED)
        self.assertFalse(result.test_payment)
        self.assertEqual(self.credit.call_count, 1)
        self.assertEqual(
            self.payment.payment_environment,
            PaymentEnvironment.LIVE,
        )

    async def test_does_not_grant_credit_for_test_channel_payment(self):
        result = await self._service(
            self._verified(payment_environment=PaymentEnvironment.TEST),
            expected_environment=PaymentEnvironment.TEST,
        ).execute(self._command())

        self.assertEqual(result.status, PaymentStatus.APPROVED)
        self.assertTrue(result.test_payment)
        self.assertEqual(self.credit.call_count, 0)
        self.assertEqual(
            self.payment.payment_environment,
            PaymentEnvironment.TEST,
        )

    async def test_rejects_unexpected_payment_environment(self):
        with self.assertRaises(BusinessRuleException):
            await self._service(
                self._verified(payment_environment=PaymentEnvironment.TEST)
            ).execute(self._command())

        self.assertEqual(self.payment.status, PaymentStatus.READY)
        self.assertEqual(self.credit.call_count, 0)

    async def test_rejects_amount_mismatch(self):
        with self.assertRaises(BusinessRuleException):
            await self._service(
                self._verified(amount=100)
            ).execute(self._command())

        self.assertEqual(self.credit.call_count, 0)

class FakePortOneResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakePortOneAsyncClient:
    def __init__(self, payload):
        self._response = FakePortOneResponse(payload)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        pass

    async def get(self, url, headers):
        return self._response


class PortOneHttpAdapterTest(unittest.IsolatedAsyncioTestCase):
    def _payload(self, channel_type):
        return {
            "id": "payment-1",
            "transactionId": "transaction-1",
            "status": "PAID",
            "amount": {"total": 6600},
            "currency": "KRW",
            "paidAt": "2026-08-17T12:00:00Z",
            "channel": {
                "pgProvider": "HTML5_INICIS",
                "type": channel_type,
            },
        }

    async def test_maps_test_channel_environment(self):
        with patch(
            "payment.adapter.outbound.payment_gateway.portone_http_adapter.httpx.AsyncClient",
            return_value=FakePortOneAsyncClient(self._payload("TEST")),
        ):
            result = await PortOneHttpAdapter("secret").get_payment(
                GetPortOnePaymentCommand(payment_id="payment-1")
            )

        self.assertEqual(result.payment_environment, PaymentEnvironment.TEST)

    async def test_rejects_unknown_channel_environment(self):
        with patch(
            "payment.adapter.outbound.payment_gateway.portone_http_adapter.httpx.AsyncClient",
            return_value=FakePortOneAsyncClient(self._payload("UNKNOWN")),
        ):
            with self.assertRaises(ExternalServiceException):
                await PortOneHttpAdapter("secret").get_payment(
                    GetPortOnePaymentCommand(payment_id="payment-1")
                )

class PaymentSettingsTest(unittest.TestCase):
    def test_reads_test_environment(self):
        with patch.dict(
            os.environ,
            {"PORTONE_EXPECTED_CHANNEL_TYPE": "TEST"},
            clear=False,
        ):
            self.assertEqual(
                required_portone_environment(),
                PaymentEnvironment.TEST,
            )

    def test_rejects_unknown_environment(self):
        with patch.dict(
            os.environ,
            {"PORTONE_EXPECTED_CHANNEL_TYPE": "UNKNOWN"},
            clear=False,
        ):
            with self.assertRaises(ExternalServiceException):
                required_portone_environment()

    def test_rejects_unsupported_environment(self):
        with patch.dict(
            os.environ,
            {"PORTONE_EXPECTED_CHANNEL_TYPE": "STAGING"},
            clear=False,
        ):
            with self.assertRaises(ExternalServiceException):
                required_portone_environment()
