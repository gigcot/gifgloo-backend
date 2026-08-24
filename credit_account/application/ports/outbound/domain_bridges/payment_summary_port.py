from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetPaymentSummariesCommand:
    user_id: str
    payment_ids: list[str]


@dataclass(frozen=True)
class PaymentSummaryResult:
    payment_id: str
    order_id: str
    amount: int
    currency: str
    credit_amount: int
    purpose: str
    status: str
    approved_at: datetime | None
    canceled_at: datetime | None


class PaymentSummaryPort(ABC):
    @abstractmethod
    async def get_summaries(
        self,
        command: GetPaymentSummariesCommand,
    ) -> list[PaymentSummaryResult]:
        pass
