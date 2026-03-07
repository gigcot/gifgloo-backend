from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotifyShareCommand:
    slug: str


class NotifySharePort(ABC):
    @abstractmethod
    def execute(self, command: NotifyShareCommand) -> None:
        pass

