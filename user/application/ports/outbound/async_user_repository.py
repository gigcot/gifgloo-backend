from abc import ABC, abstractmethod

from user.domain.aggregates.user import User


class AsyncUserRepository(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: str) -> User | None:
        pass
