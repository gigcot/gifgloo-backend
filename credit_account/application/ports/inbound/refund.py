from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RefundCreditCommand:
    user_id: str


class RefundCreditPort(ABC):
    @abstractmethod
    def execute(self, command: RefundCreditCommand) -> None:
        pass
