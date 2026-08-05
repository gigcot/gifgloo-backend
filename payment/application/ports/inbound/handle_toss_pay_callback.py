from abc import ABC, abstractmethod
from dataclasses import dataclass

from payment.domain.value_objects.payment_status import PaymentStatus


@dataclass(frozen=True)
class HandleTossPayCallbackCommand:
    status: str
    pay_token: str
    order_id: str
    transaction_id: str
    payload: dict


@dataclass(frozen=True)
class HandleTossPayCallbackResult:
    payment_id: str
    status: PaymentStatus
    already_processed: bool


class HandleTossPayCallbackPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: HandleTossPayCallbackCommand,
    ) -> HandleTossPayCallbackResult:
        pass
