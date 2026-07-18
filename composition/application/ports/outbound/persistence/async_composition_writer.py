from abc import ABC, abstractmethod

from composition.domain.aggregates.composition_job import CompositionJob


class AsyncCompositionWriter(ABC):
    @abstractmethod
    async def save(self, job: CompositionJob) -> None:
        pass
