from abc import ABC, abstractmethod


class AsyncUserVerificationPort(ABC):
    @abstractmethod
    async def is_active_user(self, user_id: str) -> bool:
        pass
