import unittest
from datetime import datetime, timedelta, timezone

from composition.application.ports.inbound.request_composition import RequestCompositionCommand
from composition.application.ports.outbound.aws.feasibility_check_port import FeasibilityCheckResult
from composition.application.services.request_composition_service import RequestCompositionService
from composition.domain.aggregates.composition_gate import CompositionGate
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import CompositionUnavailableException


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


class _GateRepository:
    def __init__(self):
        self.gate = CompositionGate(None, None, None, None)

    async def find_for_update(self):
        return self.gate

    async def update(self, gate):
        self.gate = gate


class RequestCompositionServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self, pipeline: _Pipeline):
        credit = _Credit()
        writer = _Writer()
        transaction = _Transaction()
        gate = _GateRepository()
        service = RequestCompositionService(
            user_verification=_UserVerification(),
            credit=credit,
            feasibility=_Feasibility(),
            storage=_Storage(),
            asset_save=_AssetSave(),
            pipeline_trigger=pipeline,
            composition_repo=writer,
            gate_repo=gate,
            transaction=transaction,
        )
        return service, credit, writer, transaction, gate

    async def test_deducts_one_use_and_starts_pipeline(self):
        pipeline = _Pipeline()
        service, credit, writer, transaction, gate = self._service(pipeline)

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
        self.assertEqual(gate.gate.active_job_id, result.composition_job_id)

    async def test_restores_original_use_when_pipeline_start_fails(self):
        service, credit, writer, transaction, gate = self._service(_Pipeline(fail=True))

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
        self.assertIsNone(gate.gate.active_job_id)

    async def test_rejects_second_job_without_deducting_credit(self):
        service, credit, writer, _, gate = self._service(_Pipeline())
        gate.gate.active_job_id = "existing-job"
        gate.gate.lease_until = datetime.now(timezone.utc) + timedelta(minutes=1)

        with self.assertRaises(CompositionUnavailableException):
            await service.execute(
                RequestCompositionCommand(
                    user_id="user-1",
                    gif_url="https://gif.example/source.gif",
                    target_bytes=b"\x89PNG\r\n\x1a\nimage",
                )
            )

        self.assertIsNone(credit.deducted_job_id)
        self.assertIsNone(writer.job)

    async def test_expired_job_is_refunded_before_new_job_is_reserved(self):
        service, credit, writer, _, gate = self._service(_Pipeline())
        old_job = CompositionJob("user-1")
        old_job.start_processing()
        writer.job = old_job
        gate.gate.active_job_id = old_job.id
        gate.gate.active_run_id = "expired-run"
        gate.gate.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)

        result = await service.execute(
            RequestCompositionCommand(
                user_id="user-1",
                gif_url="https://gif.example/source.gif",
                target_bytes=b"\x89PNG\r\n\x1a\nimage",
            )
        )

        self.assertEqual(old_job.status, CompositionStatus.FAILED)
        self.assertEqual(credit.refunded_job_id, old_job.id)
        self.assertEqual(gate.gate.active_job_id, result.composition_job_id)
