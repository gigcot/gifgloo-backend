from typing import Optional

from composition.application.ports.outbound.persistence.async_composition_repository import (
    AsyncCompositionRepository,
)
from composition.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSaveCommand, AssetSavePort
from composition.application.ports.outbound.aws.storage_port import StoragePort
from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from composition.application.ports.outbound.domain_bridges.user_verification_port import (
    UserVerificationPort,
)
from composition.domain.value_objects.composition_stage import CompositionStage
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.asset_category import AssetCategory
from shared.exceptions import AuthorizationException, NotFoundException
from shared.metrics import (
    COMPOSITION_COMPLETED_TOTAL,
    COMPOSITION_FAILED_TOTAL,
    CREDIT_REFUND_TOTAL,
    PIPELINE_CHECKPOINT_TOTAL,
    PIPELINE_COMPLETE_TOTAL,
    PIPELINE_FAIL_TOTAL,
)


class PipelineCallbackService:
    def __init__(
        self,
        composition_repo: AsyncCompositionRepository,
        asset_save: AssetSavePort,
        storage: StoragePort,
        credit: CreditPort,
        user_verification: UserVerificationPort,
        transaction: AsyncTransaction,
    ):
        self._composition_repo = composition_repo
        self._asset_save = asset_save
        self._storage = storage
        self._credit = credit
        self._user_verification = user_verification
        self._transaction = transaction

    async def _find_job(self, job_id: str):
        job = await self._composition_repo.find_for_update(job_id)
        if not job:
            raise NotFoundException(f"합성 작업을 찾을 수 없습니다: {job_id}")
        return job

    async def checkpoint(
        self,
        job_id: str,
        stage: CompositionStage,
        durations_ms: Optional[list[int]] = None,
        spec: Optional[dict] = None,
    ) -> None:
        job = await self._find_job(job_id)
        if job.status in (CompositionStatus.COMPLETED, CompositionStatus.FAILED):
            return
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
        await self._composition_repo.update(job)
        await self._transaction.commit()
        PIPELINE_CHECKPOINT_TOTAL.labels(stage=stage.value).inc()

    async def complete(self, job_id: str, draft_key: str, result_key: str) -> None:
        job = await self._find_job(job_id)
        if job.status in (CompositionStatus.COMPLETED, CompositionStatus.FAILED):
            return
        if not await self._user_verification.is_active_user(job.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")
        draft_asset_id = await self._asset_save.save(
            AssetSaveCommand(user_id=job.user_id, category=AssetCategory.COMPOSITION_DRAFT, url=self._storage.public_url_for(draft_key))
        )
        result_asset_id = await self._asset_save.save(
            AssetSaveCommand(user_id=job.user_id, category=AssetCategory.COMPOSITION_RESULT, url=self._storage.public_url_for(result_key))
        )
        job.complete(
            result_url=self._storage.public_url_for(result_key),
            draft_asset_id=draft_asset_id,
            result_asset_id=result_asset_id,
        )
        await self._composition_repo.update(job)
        await self._transaction.commit()
        PIPELINE_COMPLETE_TOTAL.inc()
        COMPOSITION_COMPLETED_TOTAL.inc()

    async def fail(self, job_id: str, reason: str) -> None:
        job = await self._find_job(job_id)
        if job.status in (CompositionStatus.COMPLETED, CompositionStatus.FAILED):
            return
        job.fail(reason)
        await self._composition_repo.update(job)
        await self._credit.refund(job.user_id)
        await self._transaction.commit()
        PIPELINE_FAIL_TOTAL.inc()
        COMPOSITION_FAILED_TOTAL.inc()
        CREDIT_REFUND_TOTAL.inc()
