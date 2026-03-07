from abc import ABC, abstractmethod
from typing import Optional

from user.domain.aggregates.user import User
from user.domain.value_objects.social_account import SocialAccount


class UserRepositoryPort(ABC):
    @abstractmethod
    def save(self, user: User) -> None:
        pass

    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    def find_by_social_account(self, social_account: SocialAccount) -> Optional[User]:
        pass
