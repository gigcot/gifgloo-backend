from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from payment.domain.value_objects.payment_status import PaymentStatus

@dataclass
class PayByPGPortResult:
    status: PaymentStatus
    reason: Optional[str]

class PayByPGPort(ABC):
    @abstractmethod
    def pay(self, pg_type, amount) -> PayByPGPortResult:
        pass