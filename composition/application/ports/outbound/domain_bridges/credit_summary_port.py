from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CreditSummaryResult:
    balance_before: int
    charged: int
    refunded: int
    balance_after: int


class CreditSummaryPort(ABC):
    @abstractmethod
    async def get_job_summary(
        self,
        user_id: str,
        job_id: str,
    ) -> CreditSummaryResult | None:
        pass
