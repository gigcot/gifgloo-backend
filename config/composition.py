from typing import Optional

from composition.application.services.request_composition_service import RequestCompositionService
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.ports.outbound.user_verification_port import UserVerificationPort
from composition.application.ports.outbound.credit_port import CreditPort
from composition.application.ports.outbound.asset_fetch_port import AssetFetchPort, AssetInfo
from composition.application.ports.outbound.image_composition_port import (
    ImageCompositionPort,
    ImageCompositionRequest,
    ImageCompositionResult,
)
from composition.application.ports.outbound.composition_repository import CompositionRepository
from composition.domain.aggregates.composition_job import CompositionJob
from composition.domain.value_objects.composition_image import ImageFormat


# TODO: 실제 어댑터로 교체 예정 — DB/API 연결 구현 후

class _StubUserVerification(UserVerificationPort):
    def is_active_user(self, user_id: str) -> bool:
        return True


class _StubCredit(CreditPort):
    def has_enough_credit(self, user_id: str) -> bool:
        return True

    def deduct(self, user_id: str) -> None:
        pass


class _StubAssetFetch(AssetFetchPort):
    def fetch(self, asset_id: str) -> AssetInfo:
        return AssetInfo(asset_id=asset_id, url="https://stub.url", format=ImageFormat.PNG)


class _StubImageComposition(ImageCompositionPort):
    def compose(self, request: ImageCompositionRequest) -> ImageCompositionResult:
        return ImageCompositionResult(result_url="https://stub.result.url")


class _StubCompositionRepository(CompositionRepository):
    def save(self, job: CompositionJob) -> None:
        pass

    def find_by_id(self, job_id: str) -> Optional[CompositionJob]:
        return None


def get_request_composition_service() -> RequestCompositionService:
    return RequestCompositionService(
        user_verification=_StubUserVerification(),
        credit=_StubCredit(),
        asset_fetch=_StubAssetFetch(),
        ai_model=_StubImageComposition(),
        composition_repo=_StubCompositionRepository(),
    )


def get_composition_status_service() -> GetCompositionStatusService:
    return GetCompositionStatusService(
        composition_repo=_StubCompositionRepository(),
    )
