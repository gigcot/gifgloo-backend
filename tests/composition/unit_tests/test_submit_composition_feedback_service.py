import unittest

from composition.application.ports.inbound.submit_composition_feedback import (
    SubmitCompositionFeedbackCommand,
)
from composition.application.services.submit_composition_feedback_service import (
    SubmitCompositionFeedbackService,
)
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import AuthorizationException, InvalidStateException


class _StatusReader:
    def __init__(self, job):
        self.job = job

    async def find_by_id(self, job_id: str):
        return self.job


class _FeedbackRepository:
    def __init__(self):
        self.feedback = None

    async def save(self, feedback):
        self.feedback = feedback


class _Transaction:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        pass


class SubmitCompositionFeedbackServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_saves_feedback_for_completed_owned_job(self):
        job = CompositionJob(user_id="user-1")
        job.status = CompositionStatus.COMPLETED
        repository = _FeedbackRepository()
        transaction = _Transaction()
        service = SubmitCompositionFeedbackService(
            status_reader=_StatusReader(job),
            feedback_repo=repository,
            transaction=transaction,
        )

        await service.execute(
            SubmitCompositionFeedbackCommand(
                composition_job_id=job.id,
                user_id="user-1",
                satisfied=True,
            )
        )

        self.assertEqual(repository.feedback.composition_job_id, job.id)
        self.assertTrue(repository.feedback.satisfied)
        self.assertTrue(transaction.committed)

    async def test_rejects_feedback_from_other_user(self):
        job = CompositionJob(user_id="user-1")
        job.status = CompositionStatus.COMPLETED
        service = SubmitCompositionFeedbackService(
            status_reader=_StatusReader(job),
            feedback_repo=_FeedbackRepository(),
            transaction=_Transaction(),
        )

        with self.assertRaises(AuthorizationException):
            await service.execute(
                SubmitCompositionFeedbackCommand(
                    composition_job_id=job.id,
                    user_id="user-2",
                    satisfied=False,
                )
            )

    async def test_rejects_feedback_before_completion(self):
        job = CompositionJob(user_id="user-1")
        service = SubmitCompositionFeedbackService(
            status_reader=_StatusReader(job),
            feedback_repo=_FeedbackRepository(),
            transaction=_Transaction(),
        )

        with self.assertRaises(InvalidStateException):
            await service.execute(
                SubmitCompositionFeedbackCommand(
                    composition_job_id=job.id,
                    user_id="user-1",
                    satisfied=False,
                )
            )
