from abc import ABC, abstractmethod
from dataclasses import dataclass

from user.domain.value_objects.social_account import SocialProvider
from user.domain.value_objects.signup_consent import SignupConsent
from user.domain.value_objects.acquisition import Acquisition


@dataclass
class SocialLoginCommand:
    provider: SocialProvider
    code: str
    signup_consent: SignupConsent
    acquisition: Acquisition | None = None
    anonymous_user_id: str | None = None
    anonymous_session_version: int | None = None


@dataclass
class SocialLoginResult:
    user_id: str
    is_new_user: bool
    session_version: int = 0


class SocialLoginPort(ABC):
    @abstractmethod
    def execute(self, command: SocialLoginCommand) -> SocialLoginResult:
        pass
