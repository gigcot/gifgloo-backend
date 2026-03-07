from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class UpdateEmailCommand:
    user_id: str
    email: str


class UpdateEmailPort(ABC):
    @abstractmethod
    def execute(self, command: UpdateEmailCommand) -> None:
        pass
