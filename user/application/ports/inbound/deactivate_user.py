from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeactivateUserCommand:
    user_id: str


class DeactivateUserPort(ABC):
    @abstractmethod
    def execute(self, command: DeactivateUserCommand) -> None:
        pass
