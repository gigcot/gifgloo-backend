from abc import ABC, abstractmethod


class CreditPort(ABC):
    @abstractmethod
    def has_enough_credit(self, user_id: str) -> bool:
        pass

    @abstractmethod
    def deduct(self, user_id: str) -> None:
        """크레딧 차감. 잔액 부족 시 예외 발생."""
        pass

    @abstractmethod
    def refund(self, user_id: str) -> None:
        """차감된 크레딧 환불."""
        pass
