from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from composition.domain.value_objects.composition_status import CompositionStatus
from composition.domain.value_objects.composition_stage import CompositionStage


@dataclass
class GetCompositionStatusQuery:
    composition_job_id: str
    user_id: str


@dataclass
class GetCompositionStatusResult:
    composition_job_id: str
    status: CompositionStatus
    stage: Optional[CompositionStage]
    result_url: Optional[str]
    result_asset_id: Optional[str]
    failed_reason: Optional[str]


class GetCompositionStatusPort(ABC):
    @abstractmethod
    def execute(self, query: GetCompositionStatusQuery) -> GetCompositionStatusResult:
        pass
