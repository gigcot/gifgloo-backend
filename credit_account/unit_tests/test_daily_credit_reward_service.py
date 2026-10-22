import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from credit_account.application.ports.inbound.daily_credit_reward import DailyCreditRewardCommand
from credit_account.application.services.daily_credit_reward_service import DailyCreditRewardService
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType


class Repository:
    def __init__(self):
        self.accounts = {key: CreditAccount(key, balance=0, transactions=[]) for key in ("a", "b")}
        self.records = {}
        self.calls = []

    async def find_for_update(self, user_id):
        self.calls.append("lock")
        return self.accounts[user_id]

    async def find_transaction_by_source(self, **key):
        self.calls.append("read")
        return self.records.get((key["user_id"], key["source_id"]))

    async def save(self, account):
        for transaction in account.pending_transactions:
            if transaction.transaction_type == TransactionType.CHARGE:
                self.records[account.user_id, transaction.source_id] = transaction
        account.mark_pending_changes_persisted()


class DailyCreditRewardServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = Repository()
        self.service = DailyCreditRewardService(self.repo)
        self.before_midnight = datetime(2026, 10, 22, 14, 59, 59, tzinfo=timezone.utc)
        clock = patch("credit_account.domain.aggregates.credit_account.datetime", wraps=datetime)
        clock.start().now.return_value = self.before_midnight
        self.addCleanup(clock.stop)

    async def test_three_uses_seven_days_and_separate_source(self):
        result = await self.service.claim(DailyCreditRewardCommand("a", self.before_midnight))
        self.assertTrue(result.granted)
        self.assertEqual(result.claim_date, "2026-10-22")
        self.assertEqual(result.server_now, self.before_midnight)
        self.assertEqual(result.next_claim_at, datetime(2026, 10, 22, 15, tzinfo=timezone.utc))
        self.assertEqual(result.expires_at, self.before_midnight + timedelta(days=7))
        account = self.repo.accounts["a"]
        self.assertEqual(account.balance, 30)
        self.assertEqual(account.lots[0].source_type, CreditSourceType.DAILY_REWARD)
        self.assertEqual(account.lots[0].source_id, "a:2026-10-22")
        self.assertEqual(self.repo.calls[:2], ["lock", "read"])

    async def test_retries_do_not_grant_again_or_extend_expiry(self):
        first = await self.service.claim(DailyCreditRewardCommand("a", self.before_midnight))
        duplicate = await self.service.claim(DailyCreditRewardCommand("a", self.before_midnight + timedelta(milliseconds=500)))
        self.assertTrue(duplicate.claimed)
        self.assertFalse(duplicate.granted)
        self.assertEqual(duplicate.expires_at, first.expires_at)
        self.assertEqual(self.repo.accounts["a"].balance, 30)

    async def test_korean_midnight_allows_new_claim_with_remaining_balance(self):
        await self.service.claim(DailyCreditRewardCommand("a", self.before_midnight))
        at_midnight = self.before_midnight + timedelta(seconds=1)
        status = await self.service.get_status(DailyCreditRewardCommand("a", at_midnight))
        self.assertFalse(status.claimed)
        self.assertEqual(status.claim_date, "2026-10-23")
        self.assertEqual(status.next_claim_at - status.server_now, timedelta(days=1))
        self.assertEqual(self.repo.accounts["a"].balance, 30)
        await self.service.claim(DailyCreditRewardCommand("a", at_midnight))
        self.assertEqual(self.repo.accounts["a"].balance, 60)

    async def test_other_accounts_have_independent_daily_entitlement(self):
        for user_id in ("a", "b"):
            result = await self.service.claim(DailyCreditRewardCommand(user_id, self.before_midnight))
            self.assertTrue(result.granted)
        self.assertEqual(len(self.repo.records), 2)

    async def test_status_never_grants_or_locks_and_consumption_retains_lot(self):
        command = DailyCreditRewardCommand("a", self.before_midnight)
        self.assertFalse((await self.service.get_status(command)).claimed)
        self.assertEqual(self.repo.calls, ["read"])
        self.assertEqual(self.repo.accounts["a"].balance, 0)
        await self.service.claim(command)
        account = self.repo.accounts["a"]
        account.deduct(CreditSourceType.COMPOSITION, "job-a", now=self.before_midnight)
        self.assertEqual(account.pending_transactions[0].credit_lot_id, account.lots[0].id)
        self.assertEqual(account.pending_transactions[0].source_id, "job-a")
        self.assertTrue((await self.service.get_status(command)).claimed)
