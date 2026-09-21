from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class InlineTargetImage:
    data: bytes


@dataclass(frozen=True)
class StagedTargetImage:
    upload_id: str


@dataclass
class RequestCompositionCommand:
    user_id: str
    gif_url: str
    target: InlineTargetImage | StagedTargetImage
    acknowledge_frame_reduction: bool = field(default=False)


@dataclass
class RequestCompositionResult:
    composition_job_id: str


class RequestCompositionPort(ABC):
    @abstractmethod
    async def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        pass
