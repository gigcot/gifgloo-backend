from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from credit_account.domain.aggregates.credit_account import CreditTransaction


@dataclass(frozen=True)
class GetCreditHistoryCommand:
    user_id: str
    limit: int
    cursor_created_at: datetime | None = None
    cursor_id: str | None = None


@dataclass(frozen=True)
class GetCreditHistoryResult:
    transactions: list[CreditTransaction]
    has_more: bool
    next_cursor_created_at: datetime | None
    next_cursor_id: str | None


class GetCreditHistoryPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: GetCreditHistoryCommand,
    ) -> GetCreditHistoryResult:
        pass
