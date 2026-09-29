from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GrantExperimentRewardCommand:
    user_id: str
    response_id: str
    granted_at: datetime


class CreditRewardPort(ABC):
    @abstractmethod
    async def grant(self, command: GrantExperimentRewardCommand) -> None:
        pass
