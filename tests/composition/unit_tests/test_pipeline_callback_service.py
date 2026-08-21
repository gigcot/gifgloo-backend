import unittest

from composition.application.services.pipeline_callback_service import PipelineCallbackService
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_status import CompositionStatus


class _CompositionRepository:
    def __init__(self, job):
        self.job = job
        self.saves = 0

    async def find_for_update(self, job_id):
        return self.job if self.job.id == job_id else None

    async def update(self, job):
        self.job = job
        self.saves += 1


class _AssetSave:
    async def save(self, command):
        return f"asset-{command.category.value}"


class _Storage:
    def public_url_for(self, key):
        return f"https://assets.example/{key}"


class _Credit:
    def __init__(self):
        self.refunds = []

    async def refund(self, user_id, job_id):
        self.refunds.append((user_id, job_id))


class _UserVerification:
    async def is_active_user(self, user_id):
        return True


class _Transaction:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class PipelineCallbackServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self):
        job = CompositionJob("user-1")
        job.start_processing()
        repository = _CompositionRepository(job)
        credit = _Credit()
        transaction = _Transaction()
        service = PipelineCallbackService(
            composition_repo=repository,
            asset_save=_AssetSave(),
            storage=_Storage(),
            credit=credit,
            user_verification=_UserVerification(),
            transaction=transaction,
        )
        return service, repository, credit, transaction

    async def test_complete_commits_result(self):
        service, repository, _, transaction = self._service()

        await service.complete(repository.job.id, "draft.png", "result.gif")

        self.assertEqual(repository.job.status, CompositionStatus.COMPLETED)
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)

    async def test_fail_restores_use_in_same_transaction(self):
        service, repository, credit, transaction = self._service()

        await service.fail(repository.job.id, "pipeline failed")

        self.assertEqual(repository.job.status, CompositionStatus.FAILED)
        self.assertEqual(credit.refunds, [("user-1", repository.job.id)])
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)

    async def test_duplicate_fail_does_not_restore_twice(self):
        service, repository, credit, _ = self._service()

        await service.fail(repository.job.id, "pipeline failed")
        await service.fail(repository.job.id, "pipeline failed")

        self.assertEqual(credit.refunds, [("user-1", repository.job.id)])
