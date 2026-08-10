from composition.application.ports.inbound.get_composition_status import (
    GetCompositionStatusPort,
    GetCompositionStatusQuery,
    GetCompositionStatusResult,
    CreditSettlementResult,
)
from composition.application.ports.outbound.persistence.async_composition_status_reader import (
    AsyncCompositionStatusReader,
)
from composition.application.ports.outbound.domain_bridges.credit_summary_port import (
    CreditSummaryPort,
)
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import NotFoundException, AuthorizationException


class GetCompositionStatusService(GetCompositionStatusPort):
    def __init__(
        self,
        status_reader: AsyncCompositionStatusReader,
        credit: CreditSummaryPort,
    ):
        self._status_reader = status_reader
        self._credit = credit

    async def execute(self, query: GetCompositionStatusQuery) -> GetCompositionStatusResult:
        job = await self._status_reader.find_by_id(query.composition_job_id)
        if job is None:
            raise NotFoundException("합성 작업을 찾을 수 없습니다")
        if job.user_id != query.user_id:
            raise AuthorizationException("접근 권한이 없습니다")

        credit_summary = None
        if job.status in (CompositionStatus.COMPLETED, CompositionStatus.FAILED):
            credit_summary = await self._credit.get_job_summary(
                user_id=query.user_id,
                job_id=query.composition_job_id,
            )

        return GetCompositionStatusResult(
            composition_job_id=job.id,
            status=job.status,
            stage=job.stage,
            result_url=job.result_url,
            result_asset_id=job.result_asset_id,
            failed_reason=job.failed_reason,
            credit_settlement=(
                CreditSettlementResult(
                    balance_before=credit_summary.balance_before,
                    charged=credit_summary.charged,
                    refunded=credit_summary.refunded,
                    balance_after=credit_summary.balance_after,
                )
                if credit_summary
                else None
            ),
        )
