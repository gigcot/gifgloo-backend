from abc import ABC, abstractmethod
from typing import Optional

from shared.asset_category import AssetCategory
from asset.application.dto import AssetDto, AssetResult
from asset.domain.aggregates.asset import AssetStatus, AssetType


class AssetRepositoryPort(ABC):

    @abstractmethod
    def save(self, user_id: str, asset_id: str, asset_type: AssetType, category: AssetCategory, storage_url: Optional[str], status: AssetStatus) -> None:
        pass

    @abstractmethod
    def delete(self, user_id: str, asset_id: str) -> None:
        pass

    @abstractmethod
    def get_asset_list(self, user_id: str) -> list[AssetDto]:
        pass

    @abstractmethod
    def get_url(self, user_id: str, asset_id: str) -> str:
        pass

    @abstractmethod
    def find_asset_by_id(self, asset_id: str) -> AssetResult:
        pass

    @abstractmethod
    def update_status(self, asset_id: str, status: AssetStatus) -> None:
        pass
