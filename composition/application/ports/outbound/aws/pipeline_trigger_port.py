from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PipelineTriggerCommand:
    job_id: str
    gif_url: str
    target_key: str
    user_id: str
    resume_from: str | None = None
    frame_keys: list[str] | None = None
    durations_ms: list[int] | None = None
    spec: dict | None = None
    draft_key: str | None = None


class PipelineTriggerPort(ABC):
    @abstractmethod
    async def trigger(self, command: PipelineTriggerCommand) -> None:
        pass
