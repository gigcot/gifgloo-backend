from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewLoginCommand:
    login_id: str
    password: str


@dataclass(frozen=True)
class ReviewLoginResult:
    user_id: str


class ReviewLoginPort(ABC):
    @abstractmethod
    def execute(self, command: ReviewLoginCommand) -> ReviewLoginResult:
        pass
