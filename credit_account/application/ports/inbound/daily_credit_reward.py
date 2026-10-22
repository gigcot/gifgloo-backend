from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DailyCreditRewardCommand:
    user_id: str
    requested_at: datetime


@dataclass(frozen=True)
class DailyCreditRewardResult:
    claim_date: str
    claimed: bool
    granted: bool
    server_now: datetime
    next_claim_at: datetime
    expires_at: datetime | None
