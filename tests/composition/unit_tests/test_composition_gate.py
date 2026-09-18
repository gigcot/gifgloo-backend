import unittest
from datetime import datetime, timedelta, timezone

from composition.domain.aggregates.composition_gate import CompositionGate
from shared.exceptions import CompositionUnavailableException, InvalidStateException


NOW = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)


class CompositionGateTest(unittest.TestCase):
    def test_only_one_job_can_hold_gate(self):
        gate = CompositionGate(None, None, None, None)
        gate.reserve("job-1", NOW)

        with self.assertRaises(CompositionUnavailableException):
            gate.reserve("job-2", NOW + timedelta(minutes=2))

    def test_cooldown_uses_last_edit_not_job_completion(self):
        gate = CompositionGate(None, None, None, NOW)

        with self.assertRaises(CompositionUnavailableException) as error:
            gate.reserve("job-2", NOW + timedelta(seconds=30))

        self.assertEqual(error.exception.retry_after_seconds, 35)
        gate.reserve("job-2", NOW + timedelta(seconds=65))
        self.assertEqual(gate.active_job_id, "job-2")

    def test_duplicate_and_expired_runs_cannot_edit_or_release_another_job(self):
        gate = CompositionGate(None, None, None, None)
        gate.reserve("job-1", NOW)
        gate.claim("job-1", "run-1", NOW + timedelta(seconds=1))

        with self.assertRaises(InvalidStateException):
            gate.claim("job-1", "run-2", NOW + timedelta(seconds=2))
        with self.assertRaises(InvalidStateException):
            gate.record_edit("job-1", "run-2", NOW + timedelta(seconds=2))

        gate.record_edit("job-1", "run-1", NOW + timedelta(seconds=3))
        gate.release("job-1")
        gate.reserve("job-2", NOW + timedelta(seconds=70))
        gate.release("job-1")
        self.assertEqual(gate.active_job_id, "job-2")

    def test_run_expires_after_lambda_deadline(self):
        gate = CompositionGate(None, None, None, None)
        gate.reserve("job-1", NOW)
        gate.claim("job-1", "run-1", NOW)

        with self.assertRaises(InvalidStateException):
            gate.record_edit("job-1", "run-1", NOW + timedelta(minutes=11))

    def test_later_edit_start_extends_cooldown_without_moving_it_backward(self):
        gate = CompositionGate(None, None, None, None)
        gate.reserve("job-1", NOW)
        gate.claim("job-1", "run-1", NOW)
        gate.record_edit("job-1", "run-1", NOW + timedelta(seconds=1))
        gate.record_edit("job-1", "run-1", NOW + timedelta(seconds=20), elapsed_seconds=15)
        gate.record_edit("job-1", "run-1", NOW + timedelta(seconds=21), elapsed_seconds=30)
        gate.release("job-1")

        with self.assertRaises(CompositionUnavailableException) as error:
            gate.reserve("job-2", NOW + timedelta(seconds=65))
        self.assertEqual(error.exception.retry_after_seconds, 5)
