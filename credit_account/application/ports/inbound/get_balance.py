from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class GetCreditBalanceCommand:
    user_id: str

@dataclass
class GetCreditBalanceResult:
    balance: int
    remaining_uses: int
    nearest_expires_at: datetime | None

class GetCreditBalancePort(ABC):
    @abstractmethod
    async def execute(self, command: GetCreditBalanceCommand) -> GetCreditBalanceResult:
        pass
