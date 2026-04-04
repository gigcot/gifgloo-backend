from composition.application.ports.inbound.request_composition import (
    RequestCompositionPort,
    RequestCompositionCommand,
    RequestCompositionResult,
)
from composition.domain.value_objects.composition_policy import MAX_FRAMES
from shared.exceptions import ConfirmationRequiredException, BusinessRuleException, AuthorizationException
from composition.application.ports.outbound.aws.feasibility_check_port import FeasibilityCheckPort, FeasibilityCheckCommand
from composition.application.ports.outbound.aws.storage_port import StoragePort, StorageCategory
from composition.application.ports.outbound.aws.pipeline_trigger_port import PipelineTriggerPort, PipelineTriggerCommand
from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from composition.application.ports.outbound.domain_bridges.user_verification_port import UserVerificationPort
from composition.application.ports.outbound.persistence.composition_repository import CompositionRepository
from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSavePort, AssetSaveCommand
from shared.asset_category import AssetCategory
from composition.domain.aggregates.composition_job import CompositionJob


class RequestCompositionService(RequestCompositionPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        credit: CreditPort,
        feasibility: FeasibilityCheckPort,
        storage: StoragePort,
        asset_save: AssetSavePort,
        pipeline_trigger: PipelineTriggerPort,
        composition_repo: CompositionRepository,
    ):
        self._user_verification = user_verification
        self._credit = credit
        self._feasibility = feasibility
        self._storage = storage
        self._asset_save = asset_save
        self._pipeline_trigger = pipeline_trigger
        self._composition_repo = composition_repo

    async def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        if not self._credit.has_enough_credit(command.user_id):
            raise BusinessRuleException("크레딧이 부족합니다")

        feasibility = await self._feasibility.check(FeasibilityCheckCommand(gif_url=command.gif_url))
        if not feasibility.ok:
            raise BusinessRuleException(feasibility.reason)

        if feasibility.frame_count > MAX_FRAMES and not command.acknowledge_frame_reduction:
            raise ConfirmationRequiredException(
                message=f"GIF가 {feasibility.frame_count}프레임입니다. {MAX_FRAMES}프레임으로 줄여서 진행됩니다.",
                code="FRAME_REDUCTION_REQUIRED",
                proposal={"frame_count": feasibility.frame_count, "max_frames": MAX_FRAMES},
            )

        job = CompositionJob(user_id=command.user_id)
        job.gif_url = command.gif_url

        target_key = await self._storage.upload(job.id, StorageCategory.TARGET, command.target_bytes)

        job.source_gif_asset_id = self._asset_save.save(
            AssetSaveCommand(user_id=command.user_id, category=AssetCategory.KLIPY_GIF, url=command.gif_url)
        )
        job.target_asset_id = self._asset_save.save(
            AssetSaveCommand(user_id=command.user_id, category=AssetCategory.USER_UPLOAD, url=self._storage.public_url_for(target_key))
        )

        job.start_processing()
        self._composition_repo.save(job)

        try:
            self._credit.deduct(command.user_id)
        except Exception as e:
            job.fail(str(e))
            self._composition_repo.save(job)
            raise BusinessRuleException(str(e))

        try:
            await self._pipeline_trigger.trigger(
                PipelineTriggerCommand(
                    job_id=job.id,
                    gif_url=command.gif_url,
                    user_id=command.user_id,
                )
            )
        except Exception as e:
            self._credit.refund(command.user_id)
            job.fail(str(e))
            self._composition_repo.save(job)
            raise

        return RequestCompositionResult(composition_job_id=job.id)
