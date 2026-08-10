from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from composition.domain.value_objects.composition_status import CompositionStatus
from composition.domain.value_objects.composition_stage import CompositionStage


@dataclass
class GetCompositionStatusQuery:
    composition_job_id: str
    user_id: str


@dataclass(frozen=True)
class CreditSettlementResult:
    balance_before: int
    charged: int
    refunded: int
    balance_after: int


@dataclass
class GetCompositionStatusResult:
    composition_job_id: str
    status: CompositionStatus
    stage: Optional[CompositionStage]
    result_url: Optional[str]
    result_asset_id: Optional[str]
    failed_reason: Optional[str]
    credit_settlement: Optional[CreditSettlementResult]


class GetCompositionStatusPort(ABC):
    @abstractmethod
    async def execute(self, query: GetCompositionStatusQuery) -> GetCompositionStatusResult:
        pass
