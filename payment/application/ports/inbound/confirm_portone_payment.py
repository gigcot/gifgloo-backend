from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.value_objects.payment_status import PaymentStatus


@dataclass(frozen=True)
class ConfirmPortOnePaymentCommand:
    payment_id: str
    expected_user_id: str | None


@dataclass(frozen=True)
class ConfirmPortOnePaymentResult:
    payment_id: str
    status: PaymentStatus
    already_processed: bool
    test_payment: bool


class ConfirmPortOnePaymentPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: ConfirmPortOnePaymentCommand,
    ) -> ConfirmPortOnePaymentResult:
        pass
