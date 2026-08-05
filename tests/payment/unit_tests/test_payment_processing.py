import unittest
from datetime import datetime, timezone

from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentCommand,
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
from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_status import PaymentStatus
from shared.exceptions import BusinessRuleException


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
            payload={"status": "APPROVED"},
        )

    async def test_approves_payment_and_grants_credit_in_one_commit(self):
        result = await self.service.execute(self.command())

        self.assertEqual(result.status, PaymentStatus.APPROVED)
        self.assertFalse(result.already_processed)
        self.assertEqual(self.payment.status, PaymentStatus.APPROVED)
        self.assertIsNotNone(self.payment.credit_granted_at)
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
