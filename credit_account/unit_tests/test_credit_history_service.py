import unittest
from datetime import datetime, timedelta, timezone

from credit_account.application.ports.inbound.get_history import (
    GetCreditHistoryCommand,
)
from credit_account.application.ports.inbound.get_lot_history import (
    GetCreditLotHistoryCommand,
)
from credit_account.application.ports.outbound.domain_bridges.payment_summary_port import (
    PaymentSummaryResult,
)
from credit_account.application.services.get_credit_history_service import (
    GetCreditHistoryService,
)
from credit_account.application.services.get_credit_lot_history_service import (
    GetCreditLotHistoryService,
)
from credit_account.domain.aggregates.credit_account import CreditLot, CreditTransaction
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType


class ActiveUserVerification:
    async def is_active_user(self, user_id):
        return True


class CreditHistoryRepository:
    def __init__(self, lots=None, transactions=None):
        self.lots = lots or []
        self.transactions = transactions or []
        self.lot_query = None
        self.transaction_query = None

    async def find_lot_page_by_user_id(self, **kwargs):
        self.lot_query = kwargs
        return self.lots[:kwargs["limit"]]

    async def find_transaction_page_by_user_id(self, **kwargs):
        self.transaction_query = kwargs
        return self.transactions[:kwargs["limit"]]


class PaymentSummaries:
    def __init__(self, summaries):
        self.summaries = summaries
        self.command = None

    async def get_summaries(self, command):
        self.command = command
        return self.summaries


class CreditHistoryServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_lot_expiration_boundary_is_owned_by_domain(self):
        expires_at = datetime(2026, 8, 24, tzinfo=timezone.utc)
        lot = CreditLot(
            granted_amount=50,
            remaining_amount=30,
            expires_at=expires_at,
        )

        self.assertEqual(
            lot.available_amount(expires_at - timedelta(microseconds=1)),
            30,
        )
        self.assertEqual(lot.available_amount(expires_at), 0)

    async def test_lot_history_is_bounded_and_fetches_payments_once(self):
        now = datetime.now(timezone.utc)
        lots = [
            CreditLot(
                id=f"lot-{index}",
                granted_amount=50,
                remaining_amount=30,
                expires_at=now + timedelta(days=7),
                source_type=CreditSourceType.PAYMENT,
                source_id=f"payment-{index}",
                created_at=now - timedelta(minutes=index),
            )
            for index in range(3)
        ]
        repository = CreditHistoryRepository(lots=lots)
        payments = PaymentSummaries(
            [
                PaymentSummaryResult(
                    payment_id=f"payment-{index}",
                    order_id=f"order-{index}",
                    amount=6600,
                    currency="KRW",
                    credit_amount=50,
                    purpose="COMPOSITION_PASS_PURCHASE",
                    status="APPROVED",
                    approved_at=now,
                    canceled_at=None,
                )
                for index in range(2)
            ]
        )
        service = GetCreditLotHistoryService(
            user_verification=ActiveUserVerification(),
            credit_account_repo=repository,
            payment_summaries=payments,
        )

        result = await service.execute(
            GetCreditLotHistoryCommand(user_id="user-1", limit=2)
        )

        self.assertEqual(repository.lot_query["limit"], 3)
        self.assertEqual(payments.command.payment_ids, ["payment-0", "payment-1"])
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].remaining_uses, 3)
        self.assertTrue(result.has_more)
        self.assertEqual(result.next_cursor_id, "lot-1")

    async def test_expired_lot_has_no_available_uses(self):
        now = datetime.now(timezone.utc)
        lot = CreditLot(
            id="lot-1",
            granted_amount=50,
            remaining_amount=30,
            expires_at=now - timedelta(seconds=1),
            source_type=CreditSourceType.PAYMENT,
            source_id="payment-1",
            created_at=now - timedelta(days=7),
        )
        repository = CreditHistoryRepository(lots=[lot])
        payments = PaymentSummaries(
            [
                PaymentSummaryResult(
                    payment_id="payment-1",
                    order_id="order-1",
                    amount=6600,
                    currency="KRW",
                    credit_amount=50,
                    purpose="COMPOSITION_PASS_PURCHASE",
                    status="APPROVED",
                    approved_at=lot.created_at,
                    canceled_at=None,
                )
            ]
        )
        service = GetCreditLotHistoryService(
            user_verification=ActiveUserVerification(),
            credit_account_repo=repository,
            payment_summaries=payments,
        )

        result = await service.execute(
            GetCreditLotHistoryCommand(user_id="user-1", limit=20)
        )

        self.assertTrue(result.items[0].expired)
        self.assertEqual(result.items[0].remaining_amount, 0)
        self.assertEqual(result.items[0].remaining_uses, 0)

    async def test_transaction_history_reads_only_limit_plus_one(self):
        now = datetime.now(timezone.utc)
        transactions = [
            CreditTransaction(
                id=f"transaction-{index}",
                amount=10,
                transaction_type=TransactionType.DEDUCT,
                source_type=CreditSourceType.COMPOSITION,
                source_id=f"job-{index}",
                credit_lot_id="lot-1",
                balance_after=40 - index * 10,
                created_at=now - timedelta(minutes=index),
            )
            for index in range(3)
        ]
        repository = CreditHistoryRepository(transactions=transactions)
        service = GetCreditHistoryService(
            user_verification=ActiveUserVerification(),
            credit_account_repo=repository,
        )

        result = await service.execute(
            GetCreditHistoryCommand(user_id="user-1", limit=2)
        )

        self.assertEqual(repository.transaction_query["limit"], 3)
        self.assertEqual(
            repository.transaction_query["transaction_types"],
            frozenset(
                {
                    TransactionType.CHARGE,
                    TransactionType.DEDUCT,
                    TransactionType.REFUND,
                }
            ),
        )
        self.assertEqual(len(result.transactions), 2)
        self.assertTrue(result.has_more)
        self.assertEqual(result.next_cursor_id, "transaction-1")


if __name__ == "__main__":
    unittest.main()
