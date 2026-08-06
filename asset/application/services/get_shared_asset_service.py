from asset.application.ports.inbound.get_shared_asset import (
    GetSharedAssetPort,
    GetSharedAssetQuery,
    GetSharedAssetResult,
)
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from shared.asset_category import AssetCategory
from shared.exceptions import NotFoundException


class GetSharedAssetService(GetSharedAssetPort):
    def __init__(self, asset_repo: AssetRepositoryPort):
        self._asset_repo = asset_repo

    def execute(self, query: GetSharedAssetQuery) -> GetSharedAssetResult:
        asset = self._asset_repo.find_by_share_token(query.share_token)
        if asset.category != AssetCategory.COMPOSITION_RESULT or not asset.is_available_for_composition():
            raise NotFoundException("공유 결과를 찾을 수 없습니다")
        return GetSharedAssetResult(asset_id=asset.id, result_url=asset.storage_url.value)
