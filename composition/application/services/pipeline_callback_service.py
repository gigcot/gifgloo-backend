from typing import Optional

from composition.application.ports.outbound.persistence.composition_repository import CompositionRepository
from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSavePort, AssetSaveCommand
from composition.application.ports.outbound.aws.storage_port import StoragePort
from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from composition.domain.value_objects.composition_stage import CompositionStage
from shared.asset_category import AssetCategory
from shared.exceptions import NotFoundException


class PipelineCallbackService:
    def __init__(
        self,
        composition_repo: CompositionRepository,
        asset_save: AssetSavePort,
        storage: StoragePort,
        credit: CreditPort,
    ):
        self._composition_repo = composition_repo
        self._asset_save = asset_save
        self._storage = storage
        self._credit = credit

    def _find_job(self, job_id: str):
        job = self._composition_repo.find_by_id(job_id)
        if not job:
            raise NotFoundException(f"합성 작업을 찾을 수 없습니다: {job_id}")
        return job

    def checkpoint(
        self,
        job_id: str,
        stage: CompositionStage,
        durations_ms: Optional[list[int]] = None,
        spec: Optional[dict] = None,
    ) -> None:
        job = self._find_job(job_id)
        match stage:
            case CompositionStage.EXTRACTING_FRAMES:
                job.stage_extracting_frames()
            case CompositionStage.ANALYZING:
                job.stage_analyzing(durations_ms)
            case CompositionStage.GENERATING_DRAFT:
                job.stage_generating_draft(spec)
            case CompositionStage.COMPOSITING:
                job.stage_compositing()
            case CompositionStage.BUILDING_GIF:
                job.stage_building_gif()
        self._composition_repo.save(job)

    def complete(self, job_id: str, draft_key: str, result_key: str) -> None:
        job = self._find_job(job_id)
        draft_asset_id = self._asset_save.save(
            AssetSaveCommand(user_id=job.user_id, category=AssetCategory.COMPOSITION_DRAFT, url=self._storage.public_url_for(draft_key))
        )
        result_asset_id = self._asset_save.save(
            AssetSaveCommand(user_id=job.user_id, category=AssetCategory.COMPOSITION_RESULT, url=self._storage.public_url_for(result_key))
        )
        job.complete(
            result_url=self._storage.public_url_for(result_key),
            draft_asset_id=draft_asset_id,
            result_asset_id=result_asset_id,
        )
        self._composition_repo.save(job)

    def fail(self, job_id: str, reason: str) -> None:
        job = self._find_job(job_id)
        self._credit.refund(job.user_id)
        job.fail(reason)
        self._composition_repo.save(job)
