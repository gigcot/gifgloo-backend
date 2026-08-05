from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_status import PaymentStatus


@dataclass(frozen=True)
class ProcessVerifiedPaymentCommand:
    provider: PaymentProvider
    external_event_id: str
    event_type: str
    order_id: str
    provider_payment_id: str
    provider_transaction_id: str | None
    amount: int
    currency: str
    approved_at: datetime
    payload: dict


@dataclass(frozen=True)
class ProcessVerifiedPaymentResult:
    payment_id: str
    status: PaymentStatus
    already_processed: bool


class ProcessVerifiedPaymentPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: ProcessVerifiedPaymentCommand,
    ) -> ProcessVerifiedPaymentResult:
        pass
