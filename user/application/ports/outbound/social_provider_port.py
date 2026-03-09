from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from user.domain.value_objects.social_account import SocialProvider


@dataclass
class SocialUserInfo:
    provider: SocialProvider
    provider_id: str
    email: Optional[str]


class SocialProviderPort(ABC):
    @abstractmethod
    def get_user_info(self, auth_code: str) -> SocialUserInfo:
        pass
