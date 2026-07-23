from composition.application.ports.inbound.get_composition_status import (
    GetCompositionStatusPort,
    GetCompositionStatusQuery,
    GetCompositionStatusResult,
)
from composition.application.ports.outbound.persistence.async_composition_status_reader import (
    AsyncCompositionStatusReader,
)
from shared.exceptions import NotFoundException, AuthorizationException


class GetCompositionStatusService(GetCompositionStatusPort):
    def __init__(self, status_reader: AsyncCompositionStatusReader):
        self._status_reader = status_reader

    async def execute(self, query: GetCompositionStatusQuery) -> GetCompositionStatusResult:
        job = await self._status_reader.find_by_id(query.composition_job_id)
        if job is None:
            raise NotFoundException("합성 작업을 찾을 수 없습니다")
        if job.user_id != query.user_id:
            raise AuthorizationException("접근 권한이 없습니다")

        return GetCompositionStatusResult(
            composition_job_id=job.id,
            status=job.status,
            stage=job.stage,
            result_url=job.result_url,
            result_asset_id=job.result_asset_id,
            failed_reason=job.failed_reason,
        )
