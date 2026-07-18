from abc import ABC, abstractmethod

from asset.domain.aggregates.asset import AssetStatus, AssetType
from shared.asset_category import AssetCategory


class AsyncAssetRepository(ABC):
    @abstractmethod
    async def save(
        self,
        user_id: str,
        asset_id: str,
        asset_type: AssetType,
        category: AssetCategory,
        storage_url: str,
        status: AssetStatus,
    ) -> None:
        pass
