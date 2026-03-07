from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class DeductCreditCommand:
    user_id: str

class DeductCreditPort(ABC):
    @abstractmethod
    def execute(self, command: DeductCreditCommand) -> None:
        pass