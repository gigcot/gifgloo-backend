from abc import ABC, abstractmethod
from datetime import datetime

from composition.domain.aggregates.composition_gate import CompositionGate


class CompositionGateRepository(ABC):
    @abstractmethod
    async def has_active_lease(self, now: datetime) -> bool:
        pass

    @abstractmethod
    async def find_expired_job_id(self, now: datetime) -> str | None:
        pass

    @abstractmethod
    async def find_for_update(self) -> CompositionGate:
        pass

    @abstractmethod
    async def update(self, gate: CompositionGate) -> None:
        pass
