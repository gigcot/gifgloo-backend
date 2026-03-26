from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RequestCompositionCommand:
    user_id: str
    gif_url: str
    gif_bytes: bytes
    target_bytes: bytes


@dataclass
class RequestCompositionResult:
    composition_job_id: str
    result_url: str


class RequestCompositionPort(ABC):
    @abstractmethod
    async def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        pass
