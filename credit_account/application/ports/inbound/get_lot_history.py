from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GetCreditLotHistoryCommand:
    user_id: str
    limit: int
    cursor_created_at: datetime | None = None
    cursor_id: str | None = None


@dataclass(frozen=True)
class CreditLotHistoryItemResult:
    lot_id: str
    payment_id: str
    granted_amount: int
    granted_uses: int
    remaining_amount: int
    remaining_uses: int
    expires_at: datetime
    expired: bool
    created_at: datetime
    order_id: str
    payment_amount: int
    currency: str
    purpose: str
    payment_status: str
    approved_at: datetime | None
    canceled_at: datetime | None


@dataclass(frozen=True)
class GetCreditLotHistoryResult:
    items: list[CreditLotHistoryItemResult]
    has_more: bool
    next_cursor_created_at: datetime | None
    next_cursor_id: str | None


class GetCreditLotHistoryPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: GetCreditLotHistoryCommand,
    ) -> GetCreditLotHistoryResult:
        pass
