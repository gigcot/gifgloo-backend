from composition.application.ports.inbound.get_composition_status import (
    GetCompositionStatusPort,
    GetCompositionStatusQuery,
    GetCompositionStatusResult,
)
from composition.application.ports.outbound.composition_repository import CompositionRepository


class GetCompositionStatusService(GetCompositionStatusPort):
    def __init__(self, composition_repo: CompositionRepository):
        self._composition_repo = composition_repo

    def execute(self, query: GetCompositionStatusQuery) -> GetCompositionStatusResult:
        job = self._composition_repo.find_by_id(query.composition_job_id)
        if not job:
            raise ValueError("합성 작업을 찾을 수 없습니다")
        if job.user_id != query.user_id:
            raise ValueError("접근 권한이 없습니다")

        return GetCompositionStatusResult(
            composition_job_id=job.id,
            status=job.status,
            result_asset_id=job.result_asset_id,
            failed_reason=job.failed_reason,
        )
