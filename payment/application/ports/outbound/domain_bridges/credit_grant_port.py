from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GrantPaymentCreditCommand:
    user_id: str
    amount: int
    payment_id: str
    granted_at: datetime


@dataclass(frozen=True)
class GrantPaymentCreditResult:
    granted: bool


class CreditGrantPort(ABC):
    @abstractmethod
    async def grant(
        self,
        command: GrantPaymentCreditCommand,
    ) -> GrantPaymentCreditResult:
        pass
