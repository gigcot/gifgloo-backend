import unittest

from payment.application.ports.inbound.create_payment_order import (
    CreatePaymentOrderCommand,
)
from payment.application.services.create_payment_order_service import (
    CreatePaymentOrderService,
)
from payment.application.ports.outbound.payment_gateway.toss_pay_gateway import (
    CreateTossPayCheckoutResult,
)
from payment.domain.value_objects.payment_status import PaymentStatus
from shared.exceptions import AuthorizationException, BusinessRuleException


class FakeUserVerification:
    def __init__(self, active: bool):
        self.active = active

    async def is_active_user(self, user_id: str) -> bool:
        return self.active


class FakePaymentRepository:
    def __init__(self):
        self.payment = None

    async def add(self, payment):
        self.payment = payment

    async def update(self, payment):
        self.payment = payment


class FakeTransaction:
    def __init__(self):
        self.commit_count = 0
        self.rollback_count = 0

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


class FakeTossPayGateway:
    def __init__(self):
        self.create_command = None

    async def create_checkout(self, command):
        self.create_command = command
        return CreateTossPayCheckoutResult(
            pay_token="pay-token-1",
            checkout_page="https://pay.toss.im/checkout/1",
        )


class CreatePaymentOrderServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_creates_ready_payment_from_trusted_pricing(self):
        repository = FakePaymentRepository()
        transaction = FakeTransaction()
        gateway = FakeTossPayGateway()
        service = CreatePaymentOrderService(
            user_verification=FakeUserVerification(active=True),
            payment_repo=repository,
            transaction=transaction,
            toss_pay_gateway=gateway,
        )

        result = await service.execute(CreatePaymentOrderCommand(
            user_id="user-1",
            product_id="credits_50",
        ))

        self.assertEqual(result.status, PaymentStatus.READY)
        self.assertEqual(result.amount, 6600)
        self.assertEqual(result.credit_amount, 50)
        self.assertEqual(result.pay_token, "pay-token-1")
        self.assertEqual(repository.payment.credit_amount, 50)
        self.assertEqual(repository.payment.provider_payment_id, "pay-token-1")
        self.assertEqual(gateway.create_command.amount, 6600)
        self.assertEqual(transaction.commit_count, 2)
        self.assertEqual(transaction.rollback_count, 0)

    async def test_rejects_inactive_user_before_creating_order(self):
        repository = FakePaymentRepository()
        transaction = FakeTransaction()
        service = CreatePaymentOrderService(
            user_verification=FakeUserVerification(active=False),
            payment_repo=repository,
            transaction=transaction,
            toss_pay_gateway=FakeTossPayGateway(),
        )

        with self.assertRaises(AuthorizationException):
            await service.execute(CreatePaymentOrderCommand(
                user_id="user-1",
                product_id="credits_50",
            ))

        self.assertIsNone(repository.payment)
        self.assertEqual(transaction.commit_count, 0)
        self.assertEqual(transaction.rollback_count, 0)

    async def test_rejects_unknown_product_before_creating_order(self):
        repository = FakePaymentRepository()
        transaction = FakeTransaction()
        gateway = FakeTossPayGateway()
        service = CreatePaymentOrderService(
            user_verification=FakeUserVerification(active=True),
            payment_repo=repository,
            transaction=transaction,
            toss_pay_gateway=gateway,
        )

        with self.assertRaises(BusinessRuleException):
            await service.execute(CreatePaymentOrderCommand(
                user_id="user-1",
                product_id="unknown",
            ))

        self.assertIsNone(repository.payment)
        self.assertIsNone(gateway.create_command)
        self.assertEqual(transaction.commit_count, 0)
