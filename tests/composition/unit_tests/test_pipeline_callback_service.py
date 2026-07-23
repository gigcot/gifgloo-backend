import unittest

from composition.application.services.pipeline_callback_service import PipelineCallbackService
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_stage import CompositionStage
from composition.domain.value_objects.composition_status import CompositionStatus


class _CompositionRepository:
    def __init__(self, job: CompositionJob):
        self.job = job
        self.saves = 0

    async def find_for_update(self, job_id: str) -> CompositionJob | None:
        return self.job if self.job.id == job_id else None

    async def update(self, job: CompositionJob) -> None:
        self.job = job
        self.saves += 1


class _AssetSave:
    def __init__(self):
        self.commands = []

    async def save(self, command) -> str:
        self.commands.append(command)
        return f"asset-{len(self.commands)}"


class _Storage:
    def public_url_for(self, key: str) -> str:
        return f"https://assets.example/{key}"


class _Credit:
    def __init__(self):
        self.refunded_user_ids = []

    async def refund(self, user_id: str) -> None:
        self.refunded_user_ids.append(user_id)


class _UserVerification:
    def __init__(self):
        self.calls = 0

    async def is_active_user(self, user_id: str) -> bool:
        self.calls += 1
        return True


class _Transaction:
    def __init__(self):
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class PipelineCallbackServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self):
        job = CompositionJob(user_id="user-1")
        job.start_processing()
        repository = _CompositionRepository(job)
        asset_save = _AssetSave()
        credit = _Credit()
        verification = _UserVerification()
        transaction = _Transaction()
        service = PipelineCallbackService(
            composition_repo=repository,
            asset_save=asset_save,
            storage=_Storage(),
            credit=credit,
            user_verification=verification,
            transaction=transaction,
        )
        return service, repository, asset_save, credit, verification, transaction

    async def test_complete_flushes_all_changes_before_one_commit(self):
        service, repository, asset_save, _, verification, transaction = self._service()

        await service.complete(repository.job.id, "draft.png", "result.gif")

        self.assertEqual(repository.job.status, CompositionStatus.COMPLETED)
        self.assertEqual(repository.saves, 1)
        self.assertEqual(len(asset_save.commands), 2)
        self.assertEqual(verification.calls, 1)
        self.assertEqual(transaction.commits, 1)

    async def test_checkpoint_uses_one_commit(self):
        service, repository, _, _, _, transaction = self._service()

        await service.checkpoint(
            repository.job.id,
            CompositionStage.EXTRACTING_FRAMES,
        )

        self.assertEqual(repository.job.stage, CompositionStage.EXTRACTING_FRAMES)
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)

    async def test_fail_refunds_credit_in_same_transaction(self):
        service, repository, _, credit, _, transaction = self._service()

        await service.fail(repository.job.id, "pipeline failed")

        self.assertEqual(repository.job.status, CompositionStatus.FAILED)
        self.assertEqual(credit.refunded_user_ids, ["user-1"])
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)

    async def test_duplicate_fail_does_not_refund_twice(self):
        service, repository, _, credit, _, transaction = self._service()

        await service.fail(repository.job.id, "pipeline failed")
        await service.fail(repository.job.id, "pipeline failed")

        self.assertEqual(credit.refunded_user_ids, ["user-1"])
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)

    async def test_duplicate_complete_does_not_create_assets_twice(self):
        service, repository, asset_save, _, _, transaction = self._service()

        await service.complete(repository.job.id, "draft.png", "result.gif")
        await service.complete(repository.job.id, "draft.png", "result.gif")

        self.assertEqual(len(asset_save.commands), 2)
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)
