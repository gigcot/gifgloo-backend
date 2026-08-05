import unittest
from datetime import datetime, timezone

from payment.application.ports.inbound.handle_toss_pay_callback import (
    HandleTossPayCallbackCommand,
)
from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentResult,
)
from payment.application.ports.outbound.payment_gateway.toss_pay_gateway import (
    GetTossPayStatusResult,
)
from payment.application.services.handle_toss_pay_callback_service import (
    HandleTossPayCallbackService,
)
from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_status import PaymentStatus
from shared.exceptions import BusinessRuleException, NotFoundException


class FakeTossPayGateway:
    def __init__(self, result: GetTossPayStatusResult):
        self.result = result
        self.status_command = None

    async def get_status(self, command):
        self.status_command = command
        return self.result


class FakeProcessVerifiedPayment:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        return ProcessVerifiedPaymentResult(
            payment_id="payment-1",
            status=PaymentStatus.APPROVED,
            already_processed=False,
        )


class FakePaymentRepository:
    def __init__(self, payment: Payment | None):
        self.payment = payment

    async def find_by_order_id(self, order_id: str):
        if self.payment is None or self.payment.order_id != order_id:
            return None
        return self.payment


class FakeTransaction:
    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


def _local_payment(pay_token: str = "pay-token-1") -> Payment:
    payment = Payment(
        user_id="user-1",
        provider=PaymentProvider.TOSS_PAY,
        amount=6600,
        credit_amount=50,
        order_id="order-1",
    )
    payment.assign_provider_payment(pay_token)
    return payment


def _verified_status(
    pay_status: str = "PAY_COMPLETE",
    pay_token: str = "pay-token-1",
) -> GetTossPayStatusResult:
    return GetTossPayStatusResult(
        order_id="order-1",
        pay_token=pay_token,
        pay_status=pay_status,
        amount=6600,
        paid_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        transaction_id="transaction-1",
    )


def _callback_command() -> HandleTossPayCallbackCommand:
    return HandleTossPayCallbackCommand(
        status="PAY_COMPLETE",
        pay_token="pay-token-1",
        order_id="order-1",
        transaction_id="transaction-1",
        payload={"status": "PAY_COMPLETE"},
    )


class HandleTossPayCallbackServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_processes_only_provider_verified_payment(self):
        gateway = FakeTossPayGateway(_verified_status())
        process_payment = FakeProcessVerifiedPayment()
        transaction = FakeTransaction()
        service = HandleTossPayCallbackService(
            toss_pay_gateway=gateway,
            process_payment=process_payment,
            payment_repo=FakePaymentRepository(_local_payment()),
            transaction=transaction,
        )

        result = await service.execute(_callback_command())

        self.assertEqual(result.status, PaymentStatus.APPROVED)
        self.assertEqual(gateway.status_command.order_id, "order-1")
        self.assertEqual(process_payment.command.provider, PaymentProvider.TOSS_PAY)
        self.assertEqual(process_payment.command.amount, 6600)
        self.assertEqual(process_payment.command.external_event_id, "transaction-1")
        self.assertEqual(transaction.commit_count, 1)
        self.assertEqual(transaction.rollback_count, 0)

    async def test_rejects_callback_when_provider_status_is_not_complete(self):
        gateway = FakeTossPayGateway(_verified_status(pay_status="PAY_STANDBY"))
        process_payment = FakeProcessVerifiedPayment()
        service = HandleTossPayCallbackService(
            toss_pay_gateway=gateway,
            process_payment=process_payment,
            payment_repo=FakePaymentRepository(_local_payment()),
            transaction=FakeTransaction(),
        )

        with self.assertRaises(BusinessRuleException):
            await service.execute(_callback_command())

        self.assertIsNone(process_payment.command)

    async def test_rejects_forged_pay_token(self):
        gateway = FakeTossPayGateway(_verified_status(pay_token="different-token"))
        process_payment = FakeProcessVerifiedPayment()
        service = HandleTossPayCallbackService(
            toss_pay_gateway=gateway,
            process_payment=process_payment,
            payment_repo=FakePaymentRepository(_local_payment()),
            transaction=FakeTransaction(),
        )

        with self.assertRaises(BusinessRuleException):
            await service.execute(_callback_command())

        self.assertIsNone(process_payment.command)

    async def test_rejects_unknown_order_without_calling_toss(self):
        gateway = FakeTossPayGateway(_verified_status())
        process_payment = FakeProcessVerifiedPayment()
        transaction = FakeTransaction()
        service = HandleTossPayCallbackService(
            toss_pay_gateway=gateway,
            process_payment=process_payment,
            payment_repo=FakePaymentRepository(None),
            transaction=transaction,
        )

        with self.assertRaises(NotFoundException):
            await service.execute(_callback_command())

        self.assertIsNone(gateway.status_command)
        self.assertIsNone(process_payment.command)
        self.assertEqual(transaction.commit_count, 0)
        self.assertEqual(transaction.rollback_count, 1)

    async def test_rejects_unknown_pay_token_without_calling_toss(self):
        gateway = FakeTossPayGateway(_verified_status())
        process_payment = FakeProcessVerifiedPayment()
        transaction = FakeTransaction()
        service = HandleTossPayCallbackService(
            toss_pay_gateway=gateway,
            process_payment=process_payment,
            payment_repo=FakePaymentRepository(_local_payment("stored-token")),
            transaction=transaction,
        )

        with self.assertRaises(BusinessRuleException):
            await service.execute(_callback_command())

        self.assertIsNone(gateway.status_command)
        self.assertIsNone(process_payment.command)
        self.assertEqual(transaction.commit_count, 0)
        self.assertEqual(transaction.rollback_count, 1)
