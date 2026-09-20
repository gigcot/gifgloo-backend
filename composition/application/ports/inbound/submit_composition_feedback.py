from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SubmitCompositionFeedbackCommand:
    composition_job_id: str
    user_id: str
    satisfied: bool


class SubmitCompositionFeedbackPort(ABC):
    @abstractmethod
    async def execute(self, command: SubmitCompositionFeedbackCommand) -> None:
        pass
