from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LogActionCommand:
    ...

@dataclass
class LogActionResult:
    ...

class LogActionPort(ABC):
    @abstractmethod
    def execute(self) -> None:
        pass
    