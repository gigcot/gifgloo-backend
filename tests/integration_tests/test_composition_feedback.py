import asyncio
import os
import unittest
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from composition.adapter.outbound.persistence.models import CompositionJobModel
from composition.adapter.outbound.persistence.sqlalchemy_async_composition_status_reader import SqlAlchemyAsyncCompositionStatusReader
from composition.adapter.outbound.persistence.sqlalchemy_async_transaction import SqlAlchemyAsyncTransaction
from composition.adapter.outbound.persistence.sqlalchemy_composition_feedback_repository import SqlAlchemyCompositionFeedbackRepository
from composition.application.ports.inbound.submit_composition_feedback import SubmitCompositionFeedbackCommand
from composition.application.services.submit_composition_feedback_service import SubmitCompositionFeedbackService
from composition.domain.entities.composition_feedback import CompositionFeedback
from shared.exceptions import InvalidStateException


class CompositionFeedbackIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        url = make_url(os.environ["ASYNC_DATABASE_URL"])
        if url.host not in ("localhost", "127.0.0.1") or not url.database.startswith("gifgloo_test"):
            raise RuntimeError("Feedback integration tests require a local gifgloo_test database")
        self.engine = create_async_engine(url, poolclass=NullPool)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        self.job_id = f"feedback-integration-{uuid4()}"
        async with self.sessions() as session:
            session.add(CompositionJobModel(
                id=self.job_id, user_id="feedback-test-owner", status="COMPLETED",
                created_at=datetime.now(timezone.utc),
            ))
            await session.commit()

    async def asyncTearDown(self):
        async with self.sessions() as session:
            await session.execute(delete(CompositionJobModel).where(CompositionJobModel.id == self.job_id))
            await session.commit()
        await self.engine.dispose()

    async def test_first_response_and_timestamps_survive_same_and_opposite_repeats(self):
        first = CompositionFeedback(self.job_id, False)
        async with self.sessions() as session:
            repository = SqlAlchemyCompositionFeedbackRepository(session)
            self.assertIsNone(await repository.find_by_job_id(self.job_id))
            self.assertTrue(await repository.create_once(first))
            await session.commit()
        for satisfied in (False, True):
            async with self.sessions() as session:
                repository = SqlAlchemyCompositionFeedbackRepository(session)
                self.assertFalse(await repository.create_once(CompositionFeedback(self.job_id, satisfied)))
                await session.commit()
        async with self.sessions() as session:
            saved = await SqlAlchemyCompositionFeedbackRepository(session).find_by_job_id(self.job_id)
            self.assertEqual(saved, first)

    async def test_concurrent_service_submissions_have_exactly_one_winner(self):
        start = asyncio.Event()

        async def submit(satisfied):
            async with self.sessions() as session:
                service = SubmitCompositionFeedbackService(
                    SqlAlchemyAsyncCompositionStatusReader(self.sessions),
                    SqlAlchemyCompositionFeedbackRepository(session),
                    SqlAlchemyAsyncTransaction(session),
                )
                await start.wait()
                try:
                    await service.execute(SubmitCompositionFeedbackCommand(
                        self.job_id, "feedback-test-owner", satisfied,
                    ))
                    return True
                except InvalidStateException:
                    return False

        answers = [False, True] * 4
        tasks = [asyncio.create_task(submit(answer)) for answer in answers]
        start.set()
        results = await asyncio.gather(*tasks)
        self.assertEqual(sum(results), 1)
        async with self.sessions() as session:
            saved = await SqlAlchemyCompositionFeedbackRepository(session).find_by_job_id(self.job_id)
            self.assertEqual(saved.satisfied, answers[results.index(True)])
