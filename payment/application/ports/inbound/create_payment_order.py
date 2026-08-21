from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.value_objects.payment_status import PaymentStatus
from payment.domain.value_objects.payment_purpose import PaymentPurpose


@dataclass(frozen=True)
class CreatePaymentOrderCommand:
    user_id: str
    product_id: str


@dataclass(frozen=True)
class CreatePaymentOrderResult:
    payment_id: str
    order_id: str
    amount: int
    credit_amount: int
    purpose: PaymentPurpose
    currency: str
    status: PaymentStatus
    order_name: str


class CreatePaymentOrderPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: CreatePaymentOrderCommand,
    ) -> CreatePaymentOrderResult:
        pass
