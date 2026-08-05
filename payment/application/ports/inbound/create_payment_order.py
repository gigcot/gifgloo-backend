from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.value_objects.payment_status import PaymentStatus


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
    currency: str
    status: PaymentStatus
    pay_token: str
    checkout_page: str


class CreatePaymentOrderPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: CreatePaymentOrderCommand,
    ) -> CreatePaymentOrderResult:
        pass
