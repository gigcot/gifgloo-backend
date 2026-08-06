from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GetUserAdminSummaryCommand:
    user_id: str


@dataclass(frozen=True)
class GetUserAdminSummaryResult:
    user_id: str
    email: str | None
    is_active: bool


class GetUserAdminSummaryPort(ABC):
    @abstractmethod
    async def execute(
        self,
        command: GetUserAdminSummaryCommand,
    ) -> GetUserAdminSummaryResult | None:
        pass
