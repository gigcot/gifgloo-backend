from abc import ABC, abstractmethod

from credit_account.domain.aggregates.credit_account import CreditAccount


class AsyncCreditAccountRepository(ABC):
    @abstractmethod
    async def save(self, account: CreditAccount) -> None:
        pass

    @abstractmethod
    async def find_credit_by_user_id(self, user_id: str, for_update: bool = False) -> CreditAccount | None:
        pass
