from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CreateTossPayCheckoutCommand:
    order_id: str
    amount: int
    product_description: str


@dataclass(frozen=True)
class CreateTossPayCheckoutResult:
    pay_token: str
    checkout_page: str


@dataclass(frozen=True)
class GetTossPayStatusCommand:
    order_id: str


@dataclass(frozen=True)
class GetTossPayStatusResult:
    order_id: str
    pay_token: str
    pay_status: str
    amount: int
    paid_at: datetime | None
    transaction_id: str | None


class TossPayGatewayPort(ABC):
    @abstractmethod
    async def create_checkout(
        self,
        command: CreateTossPayCheckoutCommand,
    ) -> CreateTossPayCheckoutResult:
        pass

    @abstractmethod
    async def get_status(
        self,
        command: GetTossPayStatusCommand,
    ) -> GetTossPayStatusResult:
        pass
