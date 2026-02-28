from composition.application.ports.inbound.request_composition import (
    RequestCompositionPort,
    RequestCompositionCommand,
    RequestCompositionResult,
)
from composition.application.ports.outbound.ai_model_port import AiCompositionRequest, AiModelPort
from composition.application.ports.outbound.asset_fetch_port import AssetFetchPort
from composition.application.ports.outbound.composition_repository import CompositionRepository
from composition.application.ports.outbound.credit_port import CreditPort
from composition.application.ports.outbound.user_verification_port import UserVerificationPort
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_image import CompositionImage, ImageRole


class RequestCompositionService(RequestCompositionPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        credit: CreditPort,
        asset_fetch: AssetFetchPort,
        ai_model: AiModelPort,
        composition_repo: CompositionRepository,
    ):
        self._user_verification = user_verification
        self._credit = credit
        self._asset_fetch = asset_fetch
        self._ai_model = ai_model
        self._composition_repo = composition_repo

    def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        # 1. 유저 유효성 확인
        if not self._user_verification.is_active_user(command.user_id):
            raise ValueError("유효하지 않은 유저입니다")

        # 2. 크레딧 확인
        if not self._credit.has_enough_credit(command.user_id):
            raise ValueError("크레딧이 부족합니다")

        # 3. 에셋 정보 조회 (포맷 포함)
        base_info = self._asset_fetch.fetch(command.base_asset_id)
        overlay_info = self._asset_fetch.fetch(command.overlay_asset_id)

        # 4. CompositionJob 생성 (도메인 규칙 적용)
        base_image = CompositionImage(
            asset_id=base_info.asset_id,
            role=ImageRole.BASE,
            format=base_info.format,
        )
        overlay_image = CompositionImage(
            asset_id=overlay_info.asset_id,
            role=ImageRole.OVERLAY,
            format=overlay_info.format,
        )
        job = CompositionJob(
            user_id=command.user_id,
            base_image=base_image,
            overlay_image=overlay_image,
        )

        # 5. 크레딧 차감
        self._credit.deduct(command.user_id)

        # 6. AI 모델 호출 및 처리
        job.start_processing()
        ai_result = self._ai_model.compose(
            AiCompositionRequest(
                base_url=base_info.url,
                overlay_url=overlay_info.url,
            )
        )

        # 7. 완료 처리 및 저장
        job.complete(ai_result.result_url)
        self._composition_repo.save(job)

        return RequestCompositionResult(composition_job_id=job.id)
