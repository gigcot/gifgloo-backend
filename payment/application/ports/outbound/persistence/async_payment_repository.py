from abc import ABC, abstractmethod

from payment.domain.aggregates.payment import Payment


class AsyncPaymentRepository(ABC):
    @abstractmethod
    async def add(self, payment: Payment) -> None:
        pass

    @abstractmethod
    async def update(self, payment: Payment) -> None:
        pass

    @abstractmethod
    async def find_by_order_id(self, order_id: str) -> Payment | None:
        pass

    @abstractmethod
    async def find_by_order_id_for_update(self, order_id: str) -> Payment | None:
        pass

    @abstractmethod
    async def find_by_id(self, payment_id: str) -> Payment | None:
        pass

    @abstractmethod
    async def find_all_by_user_id(self, user_id: str) -> list[Payment]:
        pass
