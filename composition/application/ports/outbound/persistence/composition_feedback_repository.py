from abc import ABC, abstractmethod

from composition.domain.entities.composition_feedback import CompositionFeedback


class CompositionFeedbackRepository(ABC):
    @abstractmethod
    async def create_once(self, feedback: CompositionFeedback) -> bool:
        pass

    @abstractmethod
    async def find_by_job_id(self, composition_job_id: str) -> CompositionFeedback | None:
        pass
