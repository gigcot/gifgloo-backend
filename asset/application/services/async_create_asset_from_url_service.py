import uuid

from asset.application.ports.outbound.persistence.async_asset_repository import AsyncAssetRepository
from asset.domain.aggregates.asset import Asset, AssetType
from asset.domain.value_objects.storage_url import StorageUrl
from shared.asset_category import AssetCategory
from shared.exceptions import ValidationException


class AsyncCreateAssetFromUrlService:
    def __init__(self, asset_repo: AsyncAssetRepository):
        self._asset_repo = asset_repo

    async def execute(self, user_id: str, category: AssetCategory, url: str) -> str:
        if not url:
            raise ValidationException("url은 필요합니다")

        asset_id = str(uuid.uuid4())
        asset = Asset(
            asset_id,
            user_id,
            AssetType.from_category(category),
            StorageUrl(url),
        )
        await self._asset_repo.save(
            asset.user_id,
            asset.id,
            asset.type,
            category,
            asset.storage_url.value,
            asset.status,
        )
        return asset_id
