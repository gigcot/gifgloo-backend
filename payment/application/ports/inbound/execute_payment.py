from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from payment.domain.value_objects.payment_status import PaymentStatus
from payment.domain.value_objects.pg_type import PgType

@dataclass
class ExecutePaymentCommand:
    user_id: str
    pg_type: PgType
    amount: int

@dataclass
class ExecutePaymentResult:
    status: PaymentStatus
    reason: Optional[str]
    
class ExecutePaymentPort(ABC):
    @abstractmethod
    def execute(self, command: ExecutePaymentCommand) -> ExecutePaymentResult:
        pass