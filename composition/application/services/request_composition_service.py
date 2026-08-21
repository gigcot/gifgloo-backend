from composition.application.ports.inbound.request_composition import (
    RequestCompositionCommand,
    RequestCompositionPort,
    RequestCompositionResult,
)
from composition.application.ports.outbound.aws.feasibility_check_port import (
    FeasibilityCheckCommand,
    FeasibilityCheckPort,
)
from composition.application.ports.outbound.aws.pipeline_trigger_port import (
    PipelineTriggerCommand,
    PipelineTriggerPort,
)
from composition.application.ports.outbound.aws.storage_port import StorageCategory, StoragePort
from composition.application.ports.outbound.domain_bridges.asset_save_port import (
    AssetSaveCommand,
    AssetSavePort,
)
from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from composition.application.ports.outbound.domain_bridges.user_verification_port import (
    UserVerificationPort,
)
from composition.application.ports.outbound.persistence.async_composition_repository import (
    AsyncCompositionRepository,
)
from composition.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_policy import ALLOWED_IMAGE_SIGNATURES, MAX_FRAMES
from shared.asset_category import AssetCategory
from shared.exceptions import (
    AuthorizationException,
    BusinessRuleException,
    ConfirmationRequiredException,
    InsufficientCreditException,
    NotFoundException,
    ValidationException,
)
from shared.metrics import (
    COMPOSITION_CREATED_TOTAL,
    CREDIT_DEDUCT_TOTAL,
    CREDIT_REFUND_TOTAL,
)


def _validate_image_format(data: bytes) -> None:
    for signature in ALLOWED_IMAGE_SIGNATURES:
        if data[:len(signature)] == signature:
            return
    raise ValidationException("지원하지 않는 이미지 형식입니다. PNG, JPEG만 지원합니다.")


class RequestCompositionService(RequestCompositionPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        credit: CreditPort,
        feasibility: FeasibilityCheckPort,
        storage: StoragePort,
        asset_save: AssetSavePort,
        pipeline_trigger: PipelineTriggerPort,
        composition_repo: AsyncCompositionRepository,
        transaction: AsyncTransaction,
    ):
        self._user_verification = user_verification
        self._credit = credit
        self._feasibility = feasibility
        self._storage = storage
        self._asset_save = asset_save
        self._pipeline_trigger = pipeline_trigger
        self._composition_repo = composition_repo
        self._transaction = transaction

    async def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")
        _validate_image_format(command.target_bytes)
        if not await self._credit.has_enough_credit(command.user_id):
            raise InsufficientCreditException("사용 가능한 GIF 합성 이용권이 없습니다")

        await self._transaction.rollback()
        feasibility = await self._feasibility.check(
            FeasibilityCheckCommand(gif_url=command.gif_url)
        )
        if not feasibility.ok:
            raise BusinessRuleException(feasibility.reason)
        if feasibility.frame_count > MAX_FRAMES and not command.acknowledge_frame_reduction:
            raise ConfirmationRequiredException(
                message=f"GIF가 {feasibility.frame_count}프레임입니다. {MAX_FRAMES}프레임으로 줄여서 진행됩니다.",
                code="FRAME_REDUCTION_REQUIRED",
                proposal={
                    "frame_count": feasibility.frame_count,
                    "max_frames": MAX_FRAMES,
                },
            )

        job = CompositionJob(user_id=command.user_id)
        job.gif_url = command.gif_url
        target_key = await self._storage.upload(
            job.id,
            StorageCategory.TARGET,
            command.target_bytes,
        )
        target_url = self._storage.public_url_for(target_key)
        job.source_gif_url = command.gif_url
        job.target_url = target_url

        try:
            job.source_gif_asset_id = await self._asset_save.save(
                AssetSaveCommand(
                    user_id=command.user_id,
                    category=AssetCategory.KLIPY_GIF,
                    url=command.gif_url,
                )
            )
            job.target_asset_id = await self._asset_save.save(
                AssetSaveCommand(
                    user_id=command.user_id,
                    category=AssetCategory.USER_UPLOAD,
                    url=target_url,
                )
            )
            job.start_processing()
            await self._composition_repo.add(job)
            await self._credit.deduct(command.user_id, job.id)
            COMPOSITION_CREATED_TOTAL.inc()
            CREDIT_DEDUCT_TOTAL.inc()
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        try:
            await self._pipeline_trigger.trigger(
                PipelineTriggerCommand(
                    job_id=job.id,
                    gif_url=command.gif_url,
                    target_key=target_key,
                    user_id=command.user_id,
                    max_frames=MAX_FRAMES,
                )
            )
        except Exception as exc:
            try:
                failed_job = await self._composition_repo.find_for_update(job.id)
                if failed_job is None:
                    raise NotFoundException("합성 작업을 찾을 수 없습니다") from exc
                await self._credit.refund(failed_job.user_id, failed_job.id)
                CREDIT_REFUND_TOTAL.inc()
                failed_job.fail(str(exc))
                await self._composition_repo.update(failed_job)
                await self._transaction.commit()
            except Exception:
                await self._transaction.rollback()
                raise
            raise

        return RequestCompositionResult(composition_job_id=job.id)
