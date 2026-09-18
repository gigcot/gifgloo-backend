from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil

from shared.exceptions import CompositionUnavailableException, InvalidStateException


COOLDOWN = timedelta(seconds=65)
PENDING_LEASE = timedelta(minutes=4)
RUNNING_LEASE = timedelta(minutes=11)


@dataclass
class CompositionGate:
    active_job_id: str | None
    active_run_id: str | None
    lease_until: datetime | None
    last_edit_sent_at: datetime | None

    def reserve(self, job_id: str, now: datetime) -> None:
        if self.active_job_id is not None:
            raise CompositionUnavailableException("다른 합성 작업이 진행 중입니다")
        if self.last_edit_sent_at is not None:
            remaining = (self.last_edit_sent_at + COOLDOWN - now).total_seconds()
            if remaining > 0:
                raise CompositionUnavailableException(
                    f"{ceil(remaining)}초 후 다시 시도해 주세요",
                    retry_after_seconds=ceil(remaining),
                )
        self.active_job_id = job_id
        self.active_run_id = None
        self.lease_until = now + PENDING_LEASE

    def claim(self, job_id: str, run_id: str, now: datetime) -> None:
        if self.active_job_id != job_id or self.active_run_id is not None or self.lease_until <= now:
            raise InvalidStateException("유효하지 않은 합성 실행입니다")
        self.active_run_id = run_id
        self.lease_until = now + RUNNING_LEASE

    def ensure_run(self, job_id: str, run_id: str, now: datetime) -> None:
        if self.active_job_id != job_id or self.active_run_id != run_id or self.lease_until <= now:
            raise InvalidStateException("유효하지 않은 합성 실행입니다")

    def record_edit(self, job_id: str, run_id: str, now: datetime, elapsed_seconds: float = 0) -> None:
        self.ensure_run(job_id, run_id, now)
        sent_at = now - timedelta(seconds=elapsed_seconds)
        if self.last_edit_sent_at is None or sent_at > self.last_edit_sent_at:
            self.last_edit_sent_at = sent_at

    def release(self, job_id: str) -> None:
        if self.active_job_id == job_id:
            self.active_job_id = None
            self.active_run_id = None
            self.lease_until = None
