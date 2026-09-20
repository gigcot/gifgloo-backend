from abc import ABC, abstractmethod

from composition.domain.entities.composition_feedback import CompositionFeedback


class CompositionFeedbackRepository(ABC):
    @abstractmethod
    async def save(self, feedback: CompositionFeedback) -> None:
        pass
