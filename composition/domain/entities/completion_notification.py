from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import uuid


@dataclass
class CompletionNotification:
    job_id: str
    user_id: str
    endpoint: str
    p256dh: str
    auth: str
    endpoint_hash: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    attempts: int = 0
    status: str = "pending"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    next_attempt_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24))

    def claim(self, now: datetime) -> None:
        self.attempts += 1
        self.next_attempt_at = now + timedelta(minutes=2)

    def settle(self, outcome: str, now: datetime) -> None:
        if outcome == "accepted":
            self.status = "sent"
        elif outcome == "invalid" or self.attempts >= 3:
            self.status = "failed"
        else:
            self.next_attempt_at = now + timedelta(seconds=30 * self.attempts)
        if self.status != "pending":
            self.endpoint = self.p256dh = self.auth = ""
