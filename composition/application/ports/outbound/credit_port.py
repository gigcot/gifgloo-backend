from abc import ABC, abstractmethod


class CreditPort(ABC):
    @abstractmethod
    def has_enough_credit(self, user_id: str) -> bool:
        pass

    @abstractmethod
    def deduct(self, user_id: str) -> None:
        pass
