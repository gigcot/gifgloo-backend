from abc import ABC, abstractmethod
from dataclasses import dataclass
from credit_account.domain.aggregates.credit_account import CreditTransaction

@dataclass
class GetCreditHistoryCommand:
    user_id: str

@dataclass
class GetCreditHistoryResult:
    transactions: list[CreditTransaction]

class GetCreditHistoryPort(ABC):
    @abstractmethod
    def execute(self, command: GetCreditHistoryCommand) -> GetCreditHistoryResult:
        pass