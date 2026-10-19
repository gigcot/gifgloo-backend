import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from composition.application.services.pipeline_callback_service import PipelineCallbackService
from composition.domain.aggregates.composition_gate import CompositionGate
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import CompositionUnavailableException, InvalidStateException, ValidationException


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
    def location_for(self, key, category):
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


class _GateRepository:
    def __init__(self, job_id):
        self.gate = CompositionGate(job_id, "run-1", datetime.now(timezone.utc) + timedelta(minutes=10), None)

    async def find_for_update(self):
        return self.gate

    async def find_expired_job_id(self, now):
        if self.gate.lease_until is not None and self.gate.lease_until <= now:
            return self.gate.active_job_id
        return None

    async def update(self, gate):
        self.gate = gate


class PipelineCallbackServiceTest(unittest.IsolatedAsyncioTestCase):
    def _service(self):
        job = CompositionJob("user-1")
        job.start_processing()
        repository = _CompositionRepository(job)
        credit = _Credit()
        transaction = _Transaction()
        gate = _GateRepository(job.id)
        service = PipelineCallbackService(
            composition_repo=repository,
            gate_repo=gate,
            asset_save=_AssetSave(),
            storage=_Storage(),
            credit=credit,
            user_verification=_UserVerification(),
            transaction=transaction,
        )
        return service, repository, credit, transaction, gate

    async def test_complete_commits_result(self):
        service, repository, _, transaction, gate = self._service()

        await service.complete(repository.job.id, "run-1", "draft.png", "result.gif")

        self.assertEqual(repository.job.status, CompositionStatus.COMPLETED)
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)
        self.assertIsNone(gate.gate.active_job_id)

    async def test_fail_restores_use_in_same_transaction(self):
        service, repository, credit, transaction, gate = self._service()

        await service.fail(repository.job.id, "run-1", "pipeline failed")

        self.assertEqual(repository.job.status, CompositionStatus.FAILED)
        self.assertEqual(credit.refunds, [("user-1", repository.job.id)])
        self.assertEqual(repository.saves, 1)
        self.assertEqual(transaction.commits, 1)
        self.assertIsNone(gate.gate.active_job_id)

    async def test_duplicate_fail_does_not_restore_twice(self):
        service, repository, credit, _, _ = self._service()

        await service.fail(repository.job.id, "run-1", "pipeline failed")
        with self.assertRaises(InvalidStateException):
            await service.fail(repository.job.id, "run-1", "pipeline failed")

        self.assertEqual(credit.refunds, [("user-1", repository.job.id)])

    async def test_expired_run_is_refunded_and_released(self):
        service, repository, credit, transaction, gate = self._service()
        gate.gate.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)

        await service.reconcile_expired()

        self.assertEqual(repository.job.status, CompositionStatus.FAILED)
        self.assertEqual(credit.refunds, [("user-1", repository.job.id)])
        self.assertIsNone(gate.gate.active_job_id)
        self.assertEqual(transaction.commits, 1)

        await service.reconcile_expired()
        self.assertEqual(credit.refunds, [("user-1", repository.job.id)])

    async def test_only_claimed_lambda_run_can_record_edits(self):
        service, repository, _, _, gate = self._service()
        gate.gate.active_run_id = None

        await service.start(repository.job.id, "run-1")
        await service.record_edit(repository.job.id, "run-1")

        self.assertIsNotNone(gate.gate.last_edit_sent_at)
        with self.assertRaises(InvalidStateException):
            await service.start(repository.job.id, "run-2")
        with self.assertRaises(InvalidStateException):
            await service.record_edit(repository.job.id, "run-2")

    async def test_final_callbacks_preserve_last_start_after_intermediate_callback_failure(self):
        for outcome in ("complete", "fail"):
            with self.subTest(outcome=outcome):
                service, repository, credit, transaction, gate = self._service()
                now = datetime.now(timezone.utc)
                gate.gate.last_edit_sent_at = now - timedelta(seconds=60)
                with patch("composition.application.services.pipeline_callback_service.datetime") as clock:
                    clock.now.return_value = now
                    if outcome == "complete":
                        await service.complete(repository.job.id, "run-1", "draft", "result", 2)
                    else:
                        await service.fail(repository.job.id, "run-1", "failed", 2)
                self.assertEqual(gate.gate.last_edit_sent_at, now - timedelta(seconds=2))
                self.assertEqual(transaction.commits, 1)
                self.assertEqual(len(credit.refunds), 0 if outcome == "complete" else 1)
                with self.assertRaises(CompositionUnavailableException) as error:
                    gate.gate.reserve("next", now + timedelta(seconds=12))
                self.assertEqual(error.exception.retry_after_seconds, 1)
                gate.gate.reserve("next", now + timedelta(seconds=13))

    async def test_legacy_final_callbacks_use_release_time_as_conservative_upper_bound(self):
        for outcome in ("complete", "fail"):
            with self.subTest(outcome=outcome):
                service, repository, _, _, gate = self._service()
                now = datetime.now(timezone.utc)
                gate.gate.last_edit_sent_at = now - timedelta(seconds=60)
                with patch("composition.application.services.pipeline_callback_service.datetime") as clock:
                    clock.now.return_value = now
                    if outcome == "complete":
                        await service.complete(repository.job.id, "run-1", "draft", "result")
                    else:
                        await service.fail(repository.job.id, "run-1", "failed")
                self.assertEqual(gate.gate.last_edit_sent_at, now)
                with self.assertRaises(CompositionUnavailableException):
                    gate.gate.reserve("next", now + timedelta(seconds=14))
                gate.gate.reserve("next", now + timedelta(seconds=15))

    async def test_stale_final_callbacks_cannot_change_new_run_or_refund(self):
        service, repository, credit, transaction, gate = self._service()
        await service.complete(repository.job.id, "run-1", "draft", "result", 0)
        now = datetime.now(timezone.utc) + timedelta(seconds=16)
        gate.gate.reserve("next", now)
        gate.gate.claim("next", "run-2", now)
        previous_anchor = gate.gate.last_edit_sent_at
        for outcome in ("complete", "fail"):
            with self.subTest(outcome=outcome), self.assertRaises(InvalidStateException):
                if outcome == "complete":
                    await service.complete(repository.job.id, "run-1", "draft", "result", 0)
                else:
                    await service.fail(repository.job.id, "run-1", "late failure", 0)
        self.assertEqual(gate.gate.active_run_id, "run-2")
        self.assertEqual(gate.gate.last_edit_sent_at, previous_anchor)
        self.assertEqual(repository.job.status, CompositionStatus.COMPLETED)
        self.assertEqual(credit.refunds, [])
        self.assertEqual(transaction.commits, 1)

    async def test_final_elapsed_cannot_move_existing_anchor_backward(self):
        service, repository, _, _, gate = self._service()
        now = datetime.now(timezone.utc)
        gate.gate.last_edit_sent_at = now - timedelta(seconds=1)
        with patch("composition.application.services.pipeline_callback_service.datetime") as clock:
            clock.now.return_value = now
            await service.fail(repository.job.id, "run-1", "failed", 60)
        self.assertEqual(gate.gate.last_edit_sent_at, now - timedelta(seconds=1))

    async def test_invalid_final_elapsed_is_rejected_before_refund_or_job_update(self):
        for outcome in ("complete", "fail"):
            for elapsed in (-1, float("nan"), float("inf"), 661, 1e20):
                with self.subTest(outcome=outcome, elapsed=elapsed):
                    service, repository, credit, transaction, gate = self._service()
                    with self.assertRaises(ValidationException):
                        if outcome == "complete":
                            await service.complete(repository.job.id, "run-1", "draft", "result", elapsed)
                        else:
                            await service.fail(repository.job.id, "run-1", "failed", elapsed)
                    self.assertEqual(repository.job.status, CompositionStatus.PROCESSING)
                    self.assertEqual(repository.saves, 0)
                    self.assertEqual(credit.refunds, [])
                    self.assertEqual(transaction.commits, 0)
                    self.assertEqual(gate.gate.active_run_id, "run-1")
