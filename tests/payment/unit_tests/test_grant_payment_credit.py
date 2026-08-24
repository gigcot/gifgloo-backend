import unittest
from datetime import datetime, timedelta, timezone

from credit_account.application.ports.inbound.grant_payment_credit import (
    GrantPaymentCreditCommand,
)
from credit_account.application.services.async_credit_service import AsyncCreditService
from credit_account.application.services.get_composition_credit_summary_service import (
    GetCompositionCreditSummaryService,
)
from credit_account.application.services.grant_payment_credit_service import (
    GrantPaymentCreditService,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.available_credit_summary import (
    AvailableCreditSummary,
)
from credit_account.domain.value_objects.transaction_type import TransactionType


class FakeCreditAccountRepository:
    def __init__(self):
        self.account = CreditAccount(user_id="user-1", balance=0, transactions=[])
        self.save_count = 0

    async def find_for_update(
        self,
        user_id: str,
        required_lot_id: str | None = None,
    ):
        return self.account if self.account.user_id == user_id else None

    async def find_available_summary_by_user_id(self, user_id: str, now: datetime):
        if self.account.user_id != user_id:
            return None
        return AvailableCreditSummary(
            balance=self.account.available_balance(now),
            nearest_expires_at=self.account.nearest_expiration(now),
        )

    async def exists_transaction_by_source(self, source_type, source_id):
        return any(
            transaction.source_type == source_type
            and transaction.source_id == source_id
            for transaction in self.account.transactions
        )

    async def find_transaction_by_source(
        self,
        user_id,
        transaction_type,
        source_type,
        source_id,
    ):
        return next(
            (
                transaction
                for transaction in self.account.transactions
                if self.account.user_id == user_id
                and transaction.transaction_type == transaction_type
                and transaction.source_type == source_type
                and transaction.source_id == source_id
            ),
            None,
        )

    async def find_transactions_by_source(self, user_id, source_type, source_id):
        return [
            transaction
            for transaction in self.account.transactions
            if self.account.user_id == user_id
            and transaction.source_type == source_type
            and transaction.source_id == source_id
        ]

    async def save(self, account):
        self.save_count += 1
        account.mark_pending_changes_persisted()


class GrantPaymentCreditServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_grants_seven_day_pass_for_each_payment_once(self):
        repository = FakeCreditAccountRepository()
        service = GrantPaymentCreditService(repository)
        granted_at = datetime(2026, 8, 20, tzinfo=timezone.utc)
        command = GrantPaymentCreditCommand(
            user_id="user-1",
            amount=50,
            payment_id="payment-1",
            granted_at=granted_at,
        )

        first = await service.execute(command)
        second = await service.execute(command)

        self.assertTrue(first.granted)
        self.assertFalse(second.granted)
        self.assertEqual(repository.account.balance, 50)
        self.assertEqual(repository.save_count, 1)
        self.assertEqual(len(repository.account.lots), 1)
        self.assertEqual(
            repository.account.lots[0].expires_at,
            granted_at + timedelta(days=7),
        )
        self.assertEqual(repository.account.transactions[0].balance_after, 50)


class _UserVerification:
    async def is_active_user(self, user_id: str) -> bool:
        return True


class CompositionCreditSummaryTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_summary_from_job_transactions(self):
        repository = FakeCreditAccountRepository()
        repository.account.charge(
            50,
            source_type=CreditSourceType.PAYMENT,
            source_id="payment-1",
        )
        repository.account.mark_pending_changes_persisted()
        service = AsyncCreditService(_UserVerification(), repository)
        summary_service = GetCompositionCreditSummaryService(repository)

        await service.deduct("user-1", "job-1")
        charged = await summary_service.execute("user-1", "job-1")

        self.assertEqual(charged.balance_before, 50)
        self.assertEqual(charged.charged, 10)
        self.assertEqual(charged.refunded, 0)
        self.assertEqual(charged.balance_after, 40)

        await service.refund("user-1", "job-1")
        restored = await summary_service.execute("user-1", "job-1")

        self.assertEqual(restored.balance_before, 50)
        self.assertEqual(restored.charged, 10)
        self.assertEqual(restored.refunded, 10)
        self.assertEqual(restored.balance_after, 50)


class CreditLotPolicyTest(unittest.TestCase):
    def test_new_purchase_settles_expired_balance_before_grant(self):
        account = CreditAccount("user-1", 0, [])
        expired = account.charge(
            50,
            granted_at=datetime.now(timezone.utc) - timedelta(days=8),
        )

        current = account.charge(50)

        self.assertEqual(expired.remaining_amount, 0)
        self.assertEqual(current.remaining_amount, 50)
        self.assertEqual(account.balance, 50)
        self.assertTrue(any(
            transaction.transaction_type == TransactionType.EXPIRATION
            for transaction in account.transactions
        ))

    def test_deducts_from_earliest_expiring_lot(self):
        account = CreditAccount("user-1", 0, [])
        first = account.charge(
            50,
            source_type=CreditSourceType.PAYMENT,
            source_id="payment-1",
            granted_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
        second = account.charge(
            50,
            source_type=CreditSourceType.PAYMENT,
            source_id="payment-2",
            granted_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )

        account.deduct(
            source_type=CreditSourceType.COMPOSITION,
            source_id="job-1",
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )

        self.assertEqual(first.remaining_amount, 40)
        self.assertEqual(second.remaining_amount, 50)
        self.assertEqual(account.balance, 90)

    def test_expires_only_remaining_amount_from_expired_lot(self):
        account = CreditAccount("user-1", 0, [])
        first = account.charge(
            50,
            granted_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
        second = account.charge(
            50,
            granted_at=datetime(2026, 8, 23, tzinfo=timezone.utc),
        )
        first.remaining_amount = 20
        account.balance = 70

        account.deduct(
            source_type=CreditSourceType.COMPOSITION,
            source_id="job-after-expiration",
            now=datetime(2026, 8, 28, tzinfo=timezone.utc),
        )

        self.assertEqual(first.remaining_amount, 0)
        self.assertEqual(second.remaining_amount, 40)
        self.assertEqual(account.balance, 40)
        expiration = next(
            transaction
            for transaction in account.transactions
            if transaction.transaction_type == TransactionType.EXPIRATION
        )
        self.assertEqual(expiration.transaction_type, TransactionType.EXPIRATION)
        self.assertEqual(expiration.amount, 20)
        self.assertEqual(expiration.created_at, first.expires_at)

    def test_creates_one_day_compensation_lot_when_original_lot_expired(self):
        account = CreditAccount("user-1", 0, [])
        original = account.charge(
            50,
            source_type=CreditSourceType.PAYMENT,
            source_id="payment-1",
            granted_at=datetime(2026, 8, 20, tzinfo=timezone.utc),
        )
        account.deduct(
            source_type=CreditSourceType.COMPOSITION,
            source_id="job-1",
            now=datetime(2026, 8, 26, tzinfo=timezone.utc),
        )
        failed_at = datetime(2026, 8, 28, tzinfo=timezone.utc)

        account.refund(
            original_lot_id=original.id,
            source_type=CreditSourceType.COMPOSITION,
            source_id="job-1",
            now=failed_at,
        )

        compensation = account.lots[-1]
        self.assertEqual(original.remaining_amount, 0)
        self.assertEqual(compensation.granted_amount, 10)
        self.assertEqual(compensation.remaining_amount, 10)
        self.assertEqual(compensation.expires_at, failed_at + timedelta(days=1))
        self.assertEqual(account.balance, 10)
