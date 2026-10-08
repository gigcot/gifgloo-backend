from abc import ABC, abstractmethod


class UserTransaction(ABC):
    @abstractmethod
    def lock(self, key: str) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass
