import unittest

from composition.application.ports.inbound.request_composition import RequestCompositionCommand
from composition.application.ports.outbound.aws.feasibility_check_port import FeasibilityCheckResult
from composition.application.services.request_composition_service import RequestCompositionService
from composition.domain.value_objects.composition_status import CompositionStatus


class _UserVerification:
    async def is_active_user(self, user_id: str) -> bool:
        return True


class _Credit:
    def __init__(self):
        self.deducted_job_id = None
        self.refunded_job_id = None

    async def has_enough_credit(self, user_id: str) -> bool:
        return True

    async def deduct(self, user_id: str, job_id: str) -> None:
        self.deducted_job_id = job_id

    async def refund(self, user_id: str, job_id: str) -> None:
        self.refunded_job_id = job_id


class _Feasibility:
    async def check(self, command) -> FeasibilityCheckResult:
        return FeasibilityCheckResult(ok=True, frame_count=1)


class _Storage:
    async def upload(self, job_id, category, data):
        return f"compositions/{job_id}/target.png"

    def public_url_for(self, key):
        return f"https://assets.example/{key}"


class _AssetSave:
    def __init__(self):
        self.calls = 0

    async def save(self, command):
        self.calls += 1
        return f"asset-{self.calls}"


class _Pipeline:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.commands = []

    async def trigger(self, command) -> None:
        self.commands.append(command)
        if self.fail:
            raise RuntimeError("pipeline unavailable")


class _Writer:
    def __init__(self):
        self.job = None
        self.saves = 0

    async def add(self, job):
        self.job = job
        self.saves += 1

    async def update(self, job):
        self.job = job
        self.saves += 1

    async def find_for_update(self, job_id):
        return self.job if self.job and self.job.id == job_id else None


class _Transaction:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class RequestCompositionServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self, pipeline: _Pipeline):
        credit = _Credit()
        writer = _Writer()
        transaction = _Transaction()
        service = RequestCompositionService(
            user_verification=_UserVerification(),
            credit=credit,
            feasibility=_Feasibility(),
            storage=_Storage(),
            asset_save=_AssetSave(),
            pipeline_trigger=pipeline,
            composition_repo=writer,
            transaction=transaction,
        )
        return service, credit, writer, transaction

    async def test_deducts_one_use_and_starts_pipeline(self):
        pipeline = _Pipeline()
        service, credit, writer, transaction = self._service(pipeline)

        result = await service.execute(
            RequestCompositionCommand(
                user_id="user-1",
                gif_url="https://gif.example/source.gif",
                target_bytes=b"\x89PNG\r\n\x1a\nimage",
            )
        )

        self.assertEqual(credit.deducted_job_id, result.composition_job_id)
        self.assertIsNone(credit.refunded_job_id)
        self.assertEqual(writer.job.status, CompositionStatus.PROCESSING)
        self.assertEqual(len(pipeline.commands), 1)
        self.assertEqual(transaction.commits, 1)

    async def test_restores_original_use_when_pipeline_start_fails(self):
        service, credit, writer, transaction = self._service(_Pipeline(fail=True))

        with self.assertRaisesRegex(RuntimeError, "pipeline unavailable"):
            await service.execute(
                RequestCompositionCommand(
                    user_id="user-1",
                    gif_url="https://gif.example/source.gif",
                    target_bytes=b"\x89PNG\r\n\x1a\nimage",
                )
            )

        self.assertEqual(credit.refunded_job_id, writer.job.id)
        self.assertEqual(writer.job.status, CompositionStatus.FAILED)
        self.assertEqual(transaction.commits, 2)
