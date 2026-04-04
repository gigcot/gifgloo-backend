from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RequestCompositionCommand:
    user_id: str
    gif_url: str
    target_bytes: bytes
    acknowledge_frame_reduction: bool = field(default=False)


@dataclass
class RequestCompositionResult:
    composition_job_id: str


class RequestCompositionPort(ABC):
    @abstractmethod
    async def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        pass
