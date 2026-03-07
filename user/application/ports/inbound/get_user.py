from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from user.domain.aggregates.user import UserRole, UserStatus


@dataclass
class GetUserQuery:
    user_id: str


@dataclass
class GetUserResult:
    user_id: str
    email: Optional[str]
    role: UserRole
    status: UserStatus


class GetUserPort(ABC):
    @abstractmethod
    def execute(self, query: GetUserQuery) -> GetUserResult:
        pass
