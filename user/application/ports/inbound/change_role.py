from abc import ABC, abstractmethod
from dataclasses import dataclass

from user.domain.aggregates.user import UserRole


@dataclass
class ChangeRoleCommand:
    target_user_id: str
    new_role: UserRole


class ChangeRolePort(ABC):
    @abstractmethod
    def execute(self, command: ChangeRoleCommand) -> None:
        pass
