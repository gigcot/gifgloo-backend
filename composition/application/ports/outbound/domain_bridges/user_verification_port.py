from abc import ABC, abstractmethod


class UserVerificationPort(ABC):
    @abstractmethod
    async def is_active_user(self, user_id: str) -> bool:
        pass
