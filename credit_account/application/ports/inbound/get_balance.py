from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class GetCreditBalanceCommand:
    user_id: str

@dataclass
class GetCreditBalanceResult:
    balance: int

class GetCreditBalancePort(ABC):
    @abstractmethod
    def execute(self, command: GetCreditBalanceCommand) -> GetCreditBalanceResult:
        pass