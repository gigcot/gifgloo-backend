from abc import ABC, abstractmethod


class AsyncCreditPort(ABC):
    @abstractmethod
    async def has_enough_credit(self, user_id: str) -> bool:
        pass

    @abstractmethod
    async def deduct(self, user_id: str) -> None:
        pass

    @abstractmethod
    async def refund(self, user_id: str) -> None:
        pass
