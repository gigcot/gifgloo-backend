from abc import ABC, abstractmethod
from credit_account.domain.aggregates.credit_account import CreditAccount

class CreditAccountRepositoryPort(ABC):
    @abstractmethod
    def save(self, input: CreditAccount) -> None:
        pass

    @abstractmethod
    def find_credit_by_user_id(self, user_id: str) -> CreditAccount:
        pass