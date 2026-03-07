from abc import ABC, abstractmethod


class VerifyUserPort(ABC):
    @abstractmethod
    def execute(self, user_id: str) -> bool:
        pass
