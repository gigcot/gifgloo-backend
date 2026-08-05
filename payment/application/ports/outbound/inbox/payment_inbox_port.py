from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.value_objects.payment_provider import PaymentProvider


@dataclass(frozen=True)
class AcquirePaymentInboxCommand:
    provider: PaymentProvider
    external_event_id: str
    event_type: str
    order_id: str
    payload: dict


@dataclass(frozen=True)
class AcquirePaymentInboxResult:
    already_processed: bool
    payment_id: str | None


class PaymentInboxPort(ABC):
    @abstractmethod
    async def acquire(
        self,
        command: AcquirePaymentInboxCommand,
    ) -> AcquirePaymentInboxResult:
        pass

    @abstractmethod
    async def mark_processed(
        self,
        provider: PaymentProvider,
        external_event_id: str,
        payment_id: str,
    ) -> None:
        pass
