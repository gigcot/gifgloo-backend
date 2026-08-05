from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GrantPaymentCreditCommand:
    user_id: str
    amount: int
    payment_id: str


@dataclass(frozen=True)
class GrantPaymentCreditResult:
    granted: bool


class GrantPaymentCreditPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: GrantPaymentCreditCommand,
    ) -> GrantPaymentCreditResult:
        pass
