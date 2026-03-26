from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class FeasibilityCheckCommand:
    gif_bytes: bytes
    target_bytes: bytes


@dataclass
class FeasibilityCheckResult:
    ok: bool
    reason: str | None = None  # ok=False일 때 사유


class FeasibilityCheckPort(ABC):
    @abstractmethod
    def check(self, command: FeasibilityCheckCommand) -> FeasibilityCheckResult:
        pass
