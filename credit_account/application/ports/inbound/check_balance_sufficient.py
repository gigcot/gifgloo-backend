from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CheckBalanceSufficientCommand:
    user_id: str


class CheckBalanceSufficientPort(ABC):
    @abstractmethod
    def execute(self, command: CheckBalanceSufficientCommand) -> bool:
        pass
