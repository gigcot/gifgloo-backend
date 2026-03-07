from abc import ABC, abstractmethod

from payment.domain.aggregates.payment import Payment

class PaymentRepositoryPort(ABC):
    @abstractmethod
    def save(self, input: Payment) -> None:
        pass

    @abstractmethod
    def find_payment_by_user_id(self, user_id: str) -> list[Payment]:
        pass