from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.aggregates.payment import Payment


@dataclass(frozen=True)
class GetPaymentSummariesCommand:
    user_id: str
    payment_ids: list[str]


@dataclass(frozen=True)
class GetPaymentSummariesResult:
    payments: list[Payment]


class GetPaymentSummariesPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: GetPaymentSummariesCommand,
    ) -> GetPaymentSummariesResult:
        pass
