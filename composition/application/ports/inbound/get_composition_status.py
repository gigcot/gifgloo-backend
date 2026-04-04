from abc import ABC, abstractmethod
from dataclasses import dataclass

from composition.domain.value_objects.composition_status import CompositionStatus


@dataclass
class GetCompositionStatusQuery:
    composition_job_id: str
    user_id: str


@dataclass
class GetCompositionStatusResult:
    composition_job_id: str
    status: CompositionStatus
    result_url: str | None
    result_asset_id: str | None
    failed_reason: str | None


class GetCompositionStatusPort(ABC):
    @abstractmethod
    def execute(self, query: GetCompositionStatusQuery) -> GetCompositionStatusResult:
        pass
