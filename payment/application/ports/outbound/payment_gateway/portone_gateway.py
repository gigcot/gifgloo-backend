from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from payment.domain.value_objects.payment_environment import PaymentEnvironment


@dataclass(frozen=True)
class GetPortOnePaymentCommand:
    payment_id: str


@dataclass(frozen=True)
class GetPortOnePaymentResult:
    payment_id: str
    transaction_id: str
    status: str
    amount: int
    currency: str
    paid_at: datetime
    pg_provider: str
    payment_environment: PaymentEnvironment


class PortOneGatewayPort(ABC):
    @abstractmethod
    async def get_payment(
        self,
        command: GetPortOnePaymentCommand,
    ) -> GetPortOnePaymentResult:
        pass
