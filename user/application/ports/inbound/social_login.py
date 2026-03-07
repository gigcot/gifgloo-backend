from abc import ABC, abstractmethod
from dataclasses import dataclass

from user.domain.value_objects.social_account import SocialProvider


@dataclass
class SocialLoginCommand:
    provider: SocialProvider
    access_token: str


@dataclass
class SocialLoginResult:
    user_id: str
    is_new_user: bool


class SocialLoginPort(ABC):
    @abstractmethod
    def execute(self, command: SocialLoginCommand) -> SocialLoginResult:
        pass
