from composition.application.ports.outbound.domain_bridges.credit_summary_port import (
    CreditSummaryPort,
    CreditSummaryResult,
)
from credit_account.application.services.get_composition_credit_summary_service import (
    GetCompositionCreditSummaryService,
)


class AsyncCreditSummaryAdapter(CreditSummaryPort):
    def __init__(self, credit_summary_service: GetCompositionCreditSummaryService):
        self._credit_summary_service = credit_summary_service

    async def get_job_summary(
        self,
        user_id: str,
        job_id: str,
    ) -> CreditSummaryResult | None:
        result = await self._credit_summary_service.execute(user_id, job_id)
        if result is None:
            return None
        return CreditSummaryResult(
            balance_before=result.balance_before,
            charged=result.charged,
            refunded=result.refunded,
            balance_after=result.balance_after,
        )
