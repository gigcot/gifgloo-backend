import unittest
from unittest.mock import AsyncMock

from composition.application.ports.inbound.get_composition_feedback import GetCompositionFeedbackCommand
from composition.application.services.get_composition_feedback_service import GetCompositionFeedbackService
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.entities.composition_feedback import CompositionFeedback
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import AuthorizationException, InvalidStateException, NotFoundException


class GetCompositionFeedbackServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_missing_or_existing_response_including_false(self):
        job = CompositionJob(user_id="owner")
        job.status = CompositionStatus.COMPLETED
        for satisfied in (None, False, True):
            with self.subTest(satisfied=satisfied):
                feedback = CompositionFeedback(job.id, satisfied) if satisfied is not None else None
                repository = AsyncMock(find_by_job_id=AsyncMock(return_value=feedback))
                service = GetCompositionFeedbackService(
                    AsyncMock(find_by_id=AsyncMock(return_value=job)), repository,
                )
                result = await service.execute(GetCompositionFeedbackCommand(job.id, job.user_id))
                self.assertIs(result.satisfied, satisfied)
                repository.find_by_job_id.assert_awaited_once_with(job.id)

    async def test_checks_job_owner_and_completion_before_reading_feedback(self):
        job = CompositionJob(user_id="owner")
        for found, user_id, expected in (
            (None, "owner", NotFoundException),
            (job, "another", AuthorizationException),
            (job, "owner", InvalidStateException),
        ):
            with self.subTest(expected=expected):
                repository = AsyncMock()
                service = GetCompositionFeedbackService(
                    AsyncMock(find_by_id=AsyncMock(return_value=found)), repository,
                )
                with self.assertRaises(expected):
                    await service.execute(GetCompositionFeedbackCommand(job.id, user_id))
                repository.find_by_job_id.assert_not_awaited()
