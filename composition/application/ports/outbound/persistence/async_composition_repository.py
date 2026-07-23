from abc import ABC, abstractmethod

from composition.domain.aggregates.composition_job import CompositionJob


class AsyncCompositionRepository(ABC):
    @abstractmethod
    async def add(self, job: CompositionJob) -> None:
        pass

    @abstractmethod
    async def update(self, job: CompositionJob) -> None:
        pass

    @abstractmethod
    async def find_for_update(self, job_id: str) -> CompositionJob | None:
        pass

    @abstractmethod
    async def find_all_by_user_id(
        self,
        user_id: str,
        limit: int,
        offset: int,
    ) -> list[CompositionJob]:
        pass
