from abc import ABC, abstractmethod

from credit_account.domain.aggregates.credit_account import CreditAccount


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
