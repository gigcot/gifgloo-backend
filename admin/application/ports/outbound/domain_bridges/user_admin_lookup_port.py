from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AdminUserResult:
    user_id: str
    email: str | None
    is_active: bool


class UserAdminLookupPort(ABC):
    @abstractmethod
    async def find_by_id(self, user_id: str) -> AdminUserResult | None:
        pass
