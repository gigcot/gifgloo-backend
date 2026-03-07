from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.aggregates.payment import Payment

@dataclass
class GetPaymentHistoryCommand:
    user_id: str

@dataclass
class GetPaymentHistoryResult:
    payments: list[Payment]

class GetPaymentHistoryPort(ABC):
    @abstractmethod
    def execute(self, command: GetPaymentHistoryCommand) -> GetPaymentHistoryResult:
        pass