from abc import ABC, abstractmethod


class CreditAccountInitPort(ABC):
    @abstractmethod
    def init_account(self, user_id: str) -> None:
        pass
