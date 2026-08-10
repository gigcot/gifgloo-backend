from abc import ABC, abstractmethod

from credit_account.domain.aggregates.credit_account import CreditTransaction
from credit_account.domain.value_objects.credit_source_type import CreditSourceType


class AsyncCreditSummaryReader(ABC):
    @abstractmethod
    async def find_transactions_by_source(
        self,
        user_id: str,
        source_type: CreditSourceType,
        source_id: str,
    ) -> list[CreditTransaction]:
        pass
