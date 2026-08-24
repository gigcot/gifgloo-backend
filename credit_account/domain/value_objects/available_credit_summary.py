from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AvailableCreditSummary:
    balance: int
    nearest_expires_at: datetime | None
