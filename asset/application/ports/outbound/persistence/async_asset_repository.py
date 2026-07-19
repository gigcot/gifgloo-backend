from abc import ABC, abstractmethod

from asset.domain.aggregates.asset import AssetStatus, AssetType
from asset.domain.value_objects.asset_list_item import AssetListItem
from shared.asset_category import AssetCategory


class AsyncAssetRepository(ABC):
    @abstractmethod
    async def find_all_by_user_id(
        self,
        user_id: str,
        category: AssetCategory | None,
        limit: int,
        offset: int,
    ) -> list[AssetListItem]:
        pass

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
