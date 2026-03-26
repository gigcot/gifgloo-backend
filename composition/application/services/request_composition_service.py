import asyncio

from composition.application.ports.inbound.request_composition import (
    RequestCompositionPort,
    RequestCompositionCommand,
    RequestCompositionResult,
)
from composition.application.ports.outbound.aws.feasibility_check_port import FeasibilityCheckPort, FeasibilityCheckCommand
from composition.application.ports.outbound.aws.gif_processing_port import GifProcessingPort
from composition.application.ports.outbound.ai.composition_analysis_port import CompositionAnalysisPort, CompositionAnalysisCommand
from composition.application.ports.outbound.ai.image_inpainting_port import ImageInpaintingPort, DraftGenerationCommand, FrameCompositingCommand
from composition.application.ports.outbound.aws.storage_port import StoragePort
from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from composition.application.ports.outbound.domain_bridges.user_verification_port import UserVerificationPort
from composition.application.ports.outbound.persistence.composition_repository import CompositionRepository
from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSavePort, AssetSaveCommand
from composition.domain.aggregates.composition_job import CompositionJob


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

    async def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        # 1. 유저 검증
        if not self._user_verification.is_active_user(command.user_id):
            raise ValueError("유효하지 않은 유저입니다")

        # 2. 잔액 확인
        if not self._credit.has_enough_credit(command.user_id):
            raise ValueError("크레딧이 부족합니다")

        # 3. Job 생성 + DB 저장
        job = CompositionJob(user_id=command.user_id)
        self._composition_repo.save(job)

        try:
            # 4. Feasibility check (무료)
            feasibility = self._feasibility.check(
                FeasibilityCheckCommand(
                    gif_bytes=command.gif_bytes,
                    target_bytes=command.target_bytes,
                )
            )
            if not feasibility.ok:
                job.fail(feasibility.reason)
                self._composition_repo.save(job)
                raise ValueError(feasibility.reason)

            # 5. 크레딧 차감 (여기서부터 비용 발생)
            self._credit.deduct(command.user_id)
        except ValueError:
            raise
        except Exception as e:
            job.fail(str(e))
            self._composition_repo.save(job)
            raise

        try:
            # 6. GIF 프레임 추출
            gif_result = self._gif_processor.extract_frames(command.gif_bytes)
            frames = [f.png_bytes for f in gif_result.frames]
            durations = [f.duration_ms for f in gif_result.frames]

            # 7. Composition Analysis (LLM)
            job.start_processing()
            spec = await self._analysis.analyze(
                CompositionAnalysisCommand(frames=frames, target=command.target_bytes)
            )

            # 8. Draft 생성
            draft_bytes = await self._inpainting.generate_draft(
                DraftGenerationCommand(
                    target=command.target_bytes,
                    spec=spec,
                    frames=frames if spec.draft_reference_frame is not None else None,
                )
            )

            # 9. 프레임별 병렬 합성
            async def composite_one(idx: int) -> bytes:
                return await self._inpainting.composite_frame(
                    FrameCompositingCommand(
                        frame=frames[idx],
                        draft=draft_bytes,
                        spec=spec,
                        frame_idx=idx,
                    )
                )

            composited_frames = await asyncio.gather(*[composite_one(i) for i in range(len(frames))])

            # 10. GIF 조합
            result_gif_bytes = self._gif_processor.build_gif(list(composited_frames), durations)

            # 11. R2 업로드 (target, draft, result)
            target_url = await self._storage.upload(job.id, "target", command.target_bytes)
            draft_url = await self._storage.upload(job.id, "draft", draft_bytes)
            result_url = await self._storage.upload(job.id, "result", result_gif_bytes)

            # 12. Asset 저장 (Asset 도메인 서비스 호출)
            source_gif_asset_id = self._asset_save.save(
                AssetSaveCommand(user_id=command.user_id, category="KLIPY_GIF", url=command.gif_url)
            )
            target_asset_id = self._asset_save.save(
                AssetSaveCommand(user_id=command.user_id, category="USER_UPLOAD", url=target_url)
            )
            draft_asset_id = self._asset_save.save(
                AssetSaveCommand(user_id=command.user_id, category="COMPOSITION_DRAFT", url=draft_url)
            )
            result_asset_id = self._asset_save.save(
                AssetSaveCommand(user_id=command.user_id, category="COMPOSITION_RESULT", url=result_url)
            )

            # 13. Job에 Asset 연결 + 완료 처리 + DB 저장
            job.source_gif_asset_id = source_gif_asset_id
            job.target_asset_id = target_asset_id
            job.draft_asset_id = draft_asset_id
            job.result_asset_id = result_asset_id
            job.complete(result_url)
            self._composition_repo.save(job)

        except Exception as e:
            self._credit.refund(command.user_id)
            job.fail(str(e))
            self._composition_repo.save(job)
            raise

        return RequestCompositionResult(composition_job_id=job.id, result_url=result_url)
