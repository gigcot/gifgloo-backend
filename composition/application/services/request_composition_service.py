import asyncio

from composition.application.ports.inbound.request_composition import (
    RequestCompositionPort,
    RequestCompositionCommand,
    RequestCompositionResult,
)
from composition.domain.value_objects.composition_policy import MAX_FRAMES
from shared.exceptions import ConfirmationRequiredException
from composition.application.ports.outbound.aws.feasibility_check_port import FeasibilityCheckPort, FeasibilityCheckCommand
from composition.application.ports.outbound.aws.gif_processing_port import GifProcessingPort
from composition.application.ports.outbound.ai.composition_analysis_port import CompositionAnalysisPort, CompositionAnalysisCommand
from composition.application.ports.outbound.ai.image_inpainting_port import ImageInpaintingPort, DraftGenerationCommand, FramesCompositingCommand
from composition.application.ports.outbound.aws.storage_port import StoragePort, StorageCategory
from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from composition.application.ports.outbound.domain_bridges.user_verification_port import UserVerificationPort
from composition.application.ports.outbound.persistence.composition_repository import CompositionRepository
from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSavePort, AssetSaveCommand
from shared.asset_category import AssetCategory
from composition.domain.aggregates.composition_job import CompositionJob
from shared.exceptions import AuthorizationException, BusinessRuleException


class RequestCompositionService(RequestCompositionPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        credit: CreditPort,
        feasibility: FeasibilityCheckPort,
        gif_processor: GifProcessingPort,
        analysis: CompositionAnalysisPort,
        inpainting: ImageInpaintingPort,
        storage: StoragePort,
        asset_save: AssetSavePort,
        composition_repo: CompositionRepository,
    ):
        self._user_verification = user_verification
        self._credit = credit
        self._feasibility = feasibility
        self._gif_processor = gif_processor
        self._analysis = analysis
        self._inpainting = inpainting
        self._storage = storage
        self._asset_save = asset_save
        self._composition_repo = composition_repo

    async def _save_input_assets(self, job_id: str, command: RequestCompositionCommand, target_key: str) -> tuple[str, str]:
        source_gif_asset_id = self._asset_save.save(
            AssetSaveCommand(user_id=command.user_id, category=AssetCategory.KLIPY_GIF, url=command.gif_url)
        )
        target_asset_id = self._asset_save.save(
            AssetSaveCommand(user_id=command.user_id, category=AssetCategory.USER_UPLOAD, url=self._storage.public_url_for(target_key))
        )
        return source_gif_asset_id, target_asset_id

    async def _run_pipeline(self, job: CompositionJob, command: RequestCompositionCommand) -> None:
        target_key = await self._storage.upload(job.id, StorageCategory.TARGET, command.target_bytes)

        input_asset_task = asyncio.create_task(self._save_input_assets(job.id, command, target_key))

        try:
            self._credit.deduct(command.user_id)
        except Exception as e:
            input_asset_task.cancel()
            job.fail(str(e))
            self._composition_repo.save(job)
            return

        try:
            gif_result = await self._gif_processor.extract_frames(command.gif_url, MAX_FRAMES, job.id)

            job.start_processing()
            spec = await self._analysis.analyze(
                CompositionAnalysisCommand(frame_keys=gif_result.frame_keys, target_key=target_key)
            )

            ref_frame_key = gif_result.frame_keys[spec.draft_reference_frame] if spec.draft_reference_frame is not None else None
            draft_key = self._storage.make_key(job.id, StorageCategory.DRAFT)
            await self._inpainting.generate_draft(
                DraftGenerationCommand(
                    target_key=target_key,
                    spec=spec,
                    draft_key=draft_key,
                    ref_frame_key=ref_frame_key,
                )
            )

            composited_keys = await self._inpainting.composite_frames(
                FramesCompositingCommand(
                    job_id=job.id,
                    frame_keys=gif_result.frame_keys,
                    draft_key=draft_key,
                    spec=spec,
                )
            )

            result_key = self._storage.make_key(job.id, StorageCategory.RESULT)

            (_, (source_gif_asset_id, target_asset_id)) = await asyncio.gather(
                self._gif_processor.build_gif(list(composited_keys), gif_result.durations_ms, result_key),
                input_asset_task,
            )

            draft_asset_id = self._asset_save.save(
                AssetSaveCommand(user_id=command.user_id, category=AssetCategory.COMPOSITION_DRAFT, url=self._storage.public_url_for(draft_key))
            )
            result_asset_id = self._asset_save.save(
                AssetSaveCommand(user_id=command.user_id, category=AssetCategory.COMPOSITION_RESULT, url=self._storage.public_url_for(result_key))
            )

            job.complete(self._storage.public_url_for(result_key), source_gif_asset_id, target_asset_id, draft_asset_id, result_asset_id)
            self._composition_repo.save(job)

        except Exception as e:
            if not input_asset_task.done():
                input_asset_task.cancel()
            self._credit.refund(command.user_id)
            job.fail(str(e))
            self._composition_repo.save(job)

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
        self._composition_repo.save(job)

        asyncio.create_task(self._run_pipeline(job, command))

        return RequestCompositionResult(composition_job_id=job.id)
