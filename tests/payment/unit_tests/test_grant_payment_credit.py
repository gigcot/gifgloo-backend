import unittest

from credit_account.application.ports.inbound.grant_payment_credit import (
    GrantPaymentCreditCommand,
)
from credit_account.application.services.grant_payment_credit_service import (
    GrantPaymentCreditService,
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

    async def exists_transaction_by_source(self, source_type, source_id):
        return (source_type, source_id) in self.sources

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
