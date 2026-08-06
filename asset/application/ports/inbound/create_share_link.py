from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CreateShareLinkCommand:
    user_id: str
    asset_id: str


@dataclass
class CreateShareLinkResult:
    share_token: str


class CreateShareLinkPort(ABC):
    @abstractmethod
    def execute(self, command: CreateShareLinkCommand) -> CreateShareLinkResult:
        pass
