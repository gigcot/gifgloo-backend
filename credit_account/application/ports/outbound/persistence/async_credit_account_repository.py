from abc import ABC, abstractmethod

from datetime import datetime

from credit_account.domain.aggregates.credit_account import (
    CreditAccount,
    CreditLot,
    CreditTransaction,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.available_credit_summary import (
    AvailableCreditSummary,
)
from credit_account.domain.value_objects.transaction_type import TransactionType


class AsyncCreditAccountRepository(ABC):
    @abstractmethod
    async def save(self, account: CreditAccount) -> None:
        pass

    @abstractmethod
    async def find_for_update(
        self,
        user_id: str,
        required_lot_id: str | None = None,
    ) -> CreditAccount | None:
        pass

    @abstractmethod
    async def find_available_summary_by_user_id(
        self,
        user_id: str,
        now: datetime,
    ) -> AvailableCreditSummary | None:
        pass

    @abstractmethod
    async def exists_transaction_by_source(
        self,
        source_type: CreditSourceType,
        source_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def find_transaction_by_source(
        self,
        user_id: str,
        transaction_type: TransactionType,
        source_type: CreditSourceType,
        source_id: str,
    ) -> CreditTransaction | None:
        pass

    @abstractmethod
    async def find_lot_page_by_user_id(
        self,
        user_id: str,
        source_type: CreditSourceType,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
    ) -> list[CreditLot]:
        pass

    @abstractmethod
    async def find_transaction_page_by_user_id(
        self,
        user_id: str,
        transaction_types: frozenset[TransactionType],
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
    ) -> list[CreditTransaction]:
        pass
