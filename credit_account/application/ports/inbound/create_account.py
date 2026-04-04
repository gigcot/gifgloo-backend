from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CreateCreditAccountCommand:
    user_id: str


class CreateCreditAccountPort(ABC):
    @abstractmethod
    def execute(self, command: CreateCreditAccountCommand) -> None:
        pass
