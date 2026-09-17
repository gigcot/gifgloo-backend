from abc import ABC, abstractmethod
from dataclasses import dataclass

from user.domain.value_objects.social_account import SocialProvider
from user.domain.value_objects.signup_consent import SignupConsent


@dataclass
class SocialLoginCommand:
    provider: SocialProvider
    code: str
    signup_consent: SignupConsent


@dataclass
class SocialLoginResult:
    user_id: str
    is_new_user: bool


class SocialLoginPort(ABC):
    @abstractmethod
    def execute(self, command: SocialLoginCommand) -> SocialLoginResult:
        pass
