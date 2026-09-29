import unittest
from datetime import datetime, timedelta, timezone

from credit_account.application.ports.inbound.grant_experiment_reward import (
    GrantExperimentRewardCommand,
)
from credit_account.application.services.grant_experiment_reward_service import (
    GrantExperimentRewardService,
)
from credit_account.domain.aggregates.credit_account import CreditAccount, CreditTransaction
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType


class CreditRepository:
    def __init__(self, account, existing=None):
        self.account = account
        self.existing = existing
        self.saved = None

    async def find_for_update(self, user_id, required_lot_id=None):
        return self.account

    async def find_transaction_by_source(self, **kwargs):
        return self.existing

    async def save(self, account):
        self.saved = account


class GrantExperimentRewardServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_grants_one_use_for_seven_days_with_response_source(self):
        account = CreditAccount(user_id="user-1", balance=0, transactions=[])
        repository = CreditRepository(account)
        granted_at = datetime(2026, 9, 29, 3, 0, tzinfo=timezone.utc)
        service = GrantExperimentRewardService(repository)

        await service.execute(
            GrantExperimentRewardCommand(
                user_id="user-1",
                response_id="response-1",
                granted_at=granted_at,
            )
        )

        self.assertIs(repository.saved, account)
        self.assertEqual(account.balance, 10)
        self.assertEqual(len(account.pending_lots), 1)
        self.assertEqual(
            account.pending_lots[0].expires_at,
            granted_at + timedelta(days=7),
        )
        self.assertEqual(
            account.pending_lots[0].source_type,
            CreditSourceType.EXPERIMENT,
        )
        self.assertEqual(account.pending_lots[0].source_id, "response-1")

    async def test_existing_charge_does_not_grant_again(self):
        account = CreditAccount(user_id="user-1", balance=10, transactions=[])
        repository = CreditRepository(
            account,
            existing=CreditTransaction(
                amount=10,
                transaction_type=TransactionType.CHARGE,
            ),
        )
        service = GrantExperimentRewardService(repository)

        await service.execute(
            GrantExperimentRewardCommand(
                user_id="user-1",
                response_id="response-1",
                granted_at=datetime.now(timezone.utc),
            )
        )

        self.assertIsNone(repository.saved)
        self.assertEqual(account.balance, 10)


if __name__ == "__main__":
    unittest.main()
