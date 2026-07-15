from abc import ABC, abstractmethod

from composition.domain.aggregates.composition_job import CompositionJob


class AsyncCompositionStatusReader(ABC):
    @abstractmethod
    async def find_by_id(self, job_id: str) -> CompositionJob | None:
        pass
