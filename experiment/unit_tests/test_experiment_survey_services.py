import unittest

from experiment.application.ports.inbound.get_experiment_survey_status import (
    GetExperimentSurveyStatusQuery,
)
from experiment.application.ports.inbound.submit_experiment_survey import (
    SubmitExperimentSurveyCommand,
)
from experiment.application.services.get_experiment_survey_status_service import (
    GetExperimentSurveyStatusService,
)
from experiment.application.services.submit_experiment_survey_service import (
    SubmitExperimentSurveyService,
)
from experiment.domain.value_objects.experiment_survey_answers import (
    ActualAction,
    IntendedContext,
    NonExternalUseReason,
)
from shared.exceptions import AuthorizationException, ValidationException


class Acquisition:
    def __init__(self, campaign="exp001_run01"):
        self.campaign = campaign

    async def get_campaign(self, user_id):
        return self.campaign


class Completion:
    def __init__(self, completed=True):
        self.completed = completed

    async def has_completed(self, user_id):
        return self.completed


class Responses:
    def __init__(self, existing=None, inserted=True):
        self.existing = existing
        self.inserted = inserted
        self.added = None

    async def find_by_experiment_and_user(self, experiment_code, user_id):
        return self.existing

    async def add_if_absent(self, response):
        self.added = response
        return self.inserted


class Rewards:
    def __init__(self, error=None):
        self.command = None
        self.error = error

    async def grant(self, command):
        self.command = command
        if self.error is not None:
            raise self.error


class Transaction:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def valid_command(**changes):
    values = {
        "user_id": "user-1",
        "intended_context": IntendedContext.GROUP_CHAT,
        "actual_actions": (ActualAction.SAVED,),
        "non_external_use_reason": NonExternalUseReason.PERSONAL_KEEP,
    }
    values.update(changes)
    return SubmitExperimentSurveyCommand(**values)


class ExperimentSurveyStatusServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_eligible_requires_run_campaign_and_completed_composition(self):
        service = GetExperimentSurveyStatusService(
            user_acquisition=Acquisition(),
            composition_completion=Completion(),
            response_repo=Responses(),
        )

        result = await service.execute(
            GetExperimentSurveyStatusQuery(user_id="user-1")
        )

        self.assertTrue(result.eligible)
        self.assertFalse(result.submitted)

    async def test_submitted_is_reported_separately_from_eligibility(self):
        service = GetExperimentSurveyStatusService(
            user_acquisition=Acquisition(campaign="another-run"),
            composition_completion=Completion(),
            response_repo=Responses(existing=object()),
        )

        result = await service.execute(
            GetExperimentSurveyStatusQuery(user_id="user-1")
        )

        self.assertFalse(result.eligible)
        self.assertTrue(result.submitted)


class SubmitExperimentSurveyServiceTest(unittest.IsolatedAsyncioTestCase):
    def make_service(
        self,
        acquisition=None,
        completion=None,
        responses=None,
        rewards=None,
        transaction=None,
    ):
        self.responses = responses or Responses()
        self.rewards = rewards or Rewards()
        self.transaction = transaction or Transaction()
        return SubmitExperimentSurveyService(
            user_acquisition=acquisition or Acquisition(),
            composition_completion=completion or Completion(),
            credit_reward=self.rewards,
            response_repo=self.responses,
            transaction=self.transaction,
        )

    async def test_stores_validated_answers_and_grants_reward_once(self):
        service = self.make_service()

        result = await service.execute(valid_command())

        self.assertTrue(result.submitted)
        self.assertEqual(self.responses.added.experiment_code, "EXP-001")
        self.assertEqual(
            self.responses.added.answers,
            {
                "intended_context": "group_chat",
                "actual_actions": ["saved"],
                "non_external_use_reason": "personal_keep",
            },
        )
        self.assertEqual(
            self.rewards.command.response_id,
            self.responses.added.id,
        )
        self.assertEqual(self.transaction.commits, 1)
        self.assertEqual(self.transaction.rollbacks, 0)

    async def test_existing_response_is_idempotent_without_another_reward(self):
        service = self.make_service(responses=Responses(existing=object()))

        result = await service.execute(valid_command())

        self.assertTrue(result.submitted)
        self.assertIsNone(self.rewards.command)
        self.assertEqual(self.transaction.commits, 1)

    async def test_concurrent_duplicate_insert_is_idempotent(self):
        service = self.make_service(responses=Responses(inserted=False))

        result = await service.execute(valid_command())

        self.assertTrue(result.submitted)
        self.assertIsNone(self.rewards.command)
        self.assertEqual(self.transaction.commits, 1)

    async def test_ineligible_user_is_rejected_and_rolled_back(self):
        service = self.make_service(acquisition=Acquisition(campaign=None))

        with self.assertRaises(AuthorizationException):
            await service.execute(valid_command())

        self.assertEqual(self.transaction.commits, 0)
        self.assertEqual(self.transaction.rollbacks, 1)

    async def test_reward_failure_rolls_back_response_and_credit(self):
        service = self.make_service(rewards=Rewards(error=RuntimeError("failure")))

        with self.assertRaises(RuntimeError):
            await service.execute(valid_command())

        self.assertEqual(self.transaction.commits, 0)
        self.assertEqual(self.transaction.rollbacks, 1)

    async def test_viewed_only_cannot_be_combined_with_another_action(self):
        service = self.make_service()

        with self.assertRaises(ValidationException):
            await service.execute(
                valid_command(
                    actual_actions=(ActualAction.VIEWED_ONLY, ActualAction.SAVED)
                )
            )

        self.assertEqual(self.transaction.commits, 0)
        self.assertEqual(self.transaction.rollbacks, 0)

    async def test_non_external_action_requires_reason(self):
        service = self.make_service()

        with self.assertRaises(ValidationException):
            await service.execute(
                valid_command(non_external_use_reason=None)
            )

    async def test_external_action_rejects_non_external_reason(self):
        service = self.make_service()

        with self.assertRaises(ValidationException):
            await service.execute(
                valid_command(
                    actual_actions=(ActualAction.GROUP_CHAT,),
                    non_external_use_reason=NonExternalUseReason.NO_SITUATION,
                )
            )


if __name__ == "__main__":
    unittest.main()
