from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DailyRewardResult:
    claim_date: str
    claimed: bool
    granted: bool
    server_now: datetime
    next_claim_at: datetime
    expires_at: datetime | None


class DailyRewardPort(ABC):
    @abstractmethod
    async def get_status(self, user_id: str) -> DailyRewardResult:
        pass

    @abstractmethod
    async def claim(self, user_id: str) -> DailyRewardResult:
        pass
