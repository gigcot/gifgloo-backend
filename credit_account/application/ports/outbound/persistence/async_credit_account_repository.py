from abc import ABC, abstractmethod

from credit_account.domain.aggregates.credit_account import CreditAccount, CreditTransaction
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType


class AsyncCreditAccountRepository(ABC):
    @abstractmethod
    async def save(self, account: CreditAccount) -> None:
        pass

    @abstractmethod
    async def find_for_update(self, user_id: str) -> CreditAccount | None:
        pass

    @abstractmethod
    async def find_balance_by_user_id(self, user_id: str) -> CreditAccount | None:
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
