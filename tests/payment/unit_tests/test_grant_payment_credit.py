import unittest

from credit_account.application.ports.inbound.grant_payment_credit import (
    GrantPaymentCreditCommand,
)
from credit_account.application.services.grant_payment_credit_service import (
    GrantPaymentCreditService,
)
from credit_account.application.services.async_credit_service import AsyncCreditService
from credit_account.application.services.get_composition_credit_summary_service import (
    GetCompositionCreditSummaryService,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.credit_source_type import CreditSourceType


class FakeCreditAccountRepository:
    def __init__(self):
        self.account = CreditAccount(user_id="user-1", balance=0, transactions=[])
        self.sources: set[tuple[CreditSourceType, str]] = set()
        self.save_count = 0

    async def find_for_update(self, user_id: str):
        return self.account if self.account.user_id == user_id else None

    async def find_balance_by_user_id(self, user_id: str):
        return self.account if self.account.user_id == user_id else None

    async def exists_transaction_by_source(self, source_type, source_id):
        return (source_type, source_id) in self.sources

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
        for transaction in account.pending_transactions:
            self.sources.add((transaction.source_type, transaction.source_id))
        account.mark_pending_transactions_persisted()


class GrantPaymentCreditServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_grants_each_payment_once(self):
        repository = FakeCreditAccountRepository()
        service = GrantPaymentCreditService(repository)
        command = GrantPaymentCreditCommand(
            user_id="user-1",
            amount=100,
            payment_id="payment-1",
        )

        first = await service.execute(command)
        second = await service.execute(command)

        self.assertTrue(first.granted)
        self.assertFalse(second.granted)
        self.assertEqual(repository.account.balance, 100)
        self.assertEqual(repository.save_count, 1)
        self.assertEqual(repository.account.transactions[0].balance_after, 100)


class _UserVerification:
    async def is_active_user(self, user_id: str) -> bool:
        return True


class CompositionCreditSummaryTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_summary_from_job_transactions(self):
        repository = FakeCreditAccountRepository()
        repository.account.balance = 50
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
