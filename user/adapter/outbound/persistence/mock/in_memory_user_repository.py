from typing import Optional

from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User
from user.domain.value_objects.social_account import SocialAccount


class InMemoryUserRepository(UserRepositoryPort):
    def __init__(self):
        self._store: dict[str, User] = {}

    def save(self, user: User) -> None:
        self._store[user.id] = user

    def find_by_id(self, user_id: str) -> Optional[User]:
        return self._store.get(user_id)

    def find_by_social_account(self, social_account: SocialAccount) -> Optional[User]:
        for user in self._store.values():
            if user.social_account == social_account:
                return user
        return None
