from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GetCompositionFeedbackCommand:
    composition_job_id: str
    user_id: str


@dataclass(frozen=True)
class GetCompositionFeedbackResult:
    satisfied: bool | None


class GetCompositionFeedbackPort(ABC):
    @abstractmethod
    async def execute(self, command: GetCompositionFeedbackCommand) -> GetCompositionFeedbackResult:
        pass
