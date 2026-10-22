import unittest
from unittest.mock import AsyncMock

from experiment.application.services.daily_reward_service import DailyRewardService
from experiment.unit_tests.test_experiment_survey_services import Responses, Transaction
from shared.exceptions import AuthorizationException


class DailyRewardServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_unsubmitted_user_cannot_read_or_claim_daily_reward(self):
        rewards = AsyncMock()
        transaction = Transaction()
        service = DailyRewardService(Responses(), rewards, transaction)
        for operation in (service.get_status, service.claim):
            with self.assertRaises(AuthorizationException):
                await operation("anonymous-user")
        rewards.get_status.assert_not_called()
        rewards.claim.assert_not_called()
        self.assertEqual(transaction.commits, 0)
        self.assertEqual(transaction.rollbacks, 1)

    async def test_existing_survey_allows_anonymous_and_member_ids(self):
        rewards = AsyncMock()
        transaction = Transaction()
        service = DailyRewardService(Responses(existing=object()), rewards, transaction)
        for user_id in ("anonymous-user", "member-user"):
            await service.get_status(user_id)
            rewards.get_status.assert_awaited_with(user_id)
            await service.claim(user_id)
            rewards.claim.assert_awaited_with(user_id)
        self.assertEqual(transaction.commits, 2)

    async def test_credit_or_commit_failure_rolls_back(self):
        for failure in ("credit", "commit"):
            rewards = AsyncMock()
            transaction = AsyncMock()
            if failure == "credit":
                rewards.claim.side_effect = RuntimeError("credit failed")
            else:
                transaction.commit.side_effect = RuntimeError("commit failed")
            service = DailyRewardService(Responses(existing=object()), rewards, transaction)
            with self.assertRaises(RuntimeError):
                await service.claim("user")
            transaction.rollback.assert_awaited_once()
