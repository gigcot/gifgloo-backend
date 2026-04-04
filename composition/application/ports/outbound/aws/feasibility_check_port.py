from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FeasibilityCheckCommand:
    gif_url: str


@dataclass
class FeasibilityCheckResult:
    ok: bool
    frame_count: int = 0
    reason: str | None = None  # ok=False일 때 사유


class FeasibilityCheckPort(ABC):
    @abstractmethod
    async def check(self, command: FeasibilityCheckCommand) -> FeasibilityCheckResult:
        pass
