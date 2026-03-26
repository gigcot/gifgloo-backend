from abc import ABC, abstractmethod
from typing import Optional

from composition.domain.aggregates.composition_job import CompositionJob


class CompositionRepository(ABC):
    @abstractmethod
    def save(self, job: CompositionJob) -> None:
        pass

    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[CompositionJob]:
        pass
