from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ChargeCreditCommand:
    user_id: str
    amount: int

class ChargeCreditPort(ABC):
    @abstractmethod
    def execute(self, command: ChargeCreditCommand) -> None:
        pass