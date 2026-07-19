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
        self.deducted = False
        self.refunded = False

    async def has_enough_credit(self, user_id: str) -> bool:
        return True

    async def deduct(self, user_id: str) -> None:
        self.deducted = True

    async def refund(self, user_id: str) -> None:
        self.refunded = True


class _Feasibility:
    async def check(self, command) -> FeasibilityCheckResult:
        return FeasibilityCheckResult(ok=True, frame_count=1)


class _Storage:
    async def upload(self, job_id, category, data) -> str:
        return f"target/{job_id}"

    def public_url_for(self, key: str) -> str:
        return f"https://assets.example/{key}"


class _AssetSave:
    def __init__(self):
        self.calls = 0

    async def save(self, command) -> str:
        self.calls += 1
        return f"asset-{self.calls}"


class _Pipeline:
    def __init__(self, fail: bool = False):
        self._fail = fail

    async def trigger(self, command) -> None:
        if self._fail:
            raise RuntimeError("pipeline unavailable")


class _Writer:
    def __init__(self):
        self.jobs = []

    async def add(self, job) -> None:
        self.jobs.append((job.id, job.status, job.failed_reason))

    async def update(self, job) -> None:
        self.jobs.append((job.id, job.status, job.failed_reason))


class _Transaction:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


class RequestCompositionServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self, pipeline: _Pipeline):
        credit = _Credit()
        writer = _Writer()
        transaction = _Transaction()
        return (
            RequestCompositionService(
                user_verification=_UserVerification(),
                credit=credit,
                feasibility=_Feasibility(),
                storage=_Storage(),
                asset_save=_AssetSave(),
                pipeline_trigger=pipeline,
                composition_repo=writer,
                transaction=transaction,
            ),
            credit,
            writer,
            transaction,
        )

    async def test_commits_job_assets_and_credit_before_triggering_pipeline(self):
        service, credit, writer, transaction = self._service(_Pipeline())

        result = await service.execute(
            RequestCompositionCommand(
                user_id="user-1",
                gif_url="https://gif.example/source.gif",
                target_bytes=b"\x89PNG\r\n\x1a\nimage",
            )
        )

        self.assertTrue(result.composition_job_id)
        self.assertTrue(credit.deducted)
        self.assertFalse(credit.refunded)
        self.assertEqual(writer.jobs[-1][1], CompositionStatus.PROCESSING)
        self.assertEqual(transaction.commits, 1)
        self.assertEqual(transaction.rollbacks, 1)

    async def test_refunds_credit_and_marks_job_failed_when_pipeline_trigger_fails(self):
        service, credit, writer, transaction = self._service(_Pipeline(fail=True))

        with self.assertRaisesRegex(RuntimeError, "pipeline unavailable"):
            await service.execute(
                RequestCompositionCommand(
                    user_id="user-1",
                    gif_url="https://gif.example/source.gif",
                    target_bytes=b"\x89PNG\r\n\x1a\nimage",
                )
            )

        self.assertTrue(credit.deducted)
        self.assertTrue(credit.refunded)
        self.assertEqual(writer.jobs[-1][1], CompositionStatus.FAILED)
        self.assertEqual(transaction.commits, 2)
