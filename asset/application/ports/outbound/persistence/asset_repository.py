from abc import ABC, abstractmethod
from typing import Optional
from enum import Enum

from asset.application.dto import AssetCategory, AssetDto, AssetResult

class AssetRepositoryPort(ABC):

    @abstractmethod
    def save(self, user_id: str, asset_id: str, asset_type: str, category: AssetCategory, storage_url: Optional[str], status: str) -> None:
        pass

    @abstractmethod
    def delete(self, user_id: str, asset_id: str) -> None:
        pass

    @abstractmethod
    def get_asset_list(self, user_id: str) -> list[AssetDto]:
        pass

    @abstractmethod
    def get_url(self, user_id: str, asset_id:str) -> str:
        pass
    
    @abstractmethod
    def find_asset_by_id(self, asset_id: str) -> AssetResult:
        pass
    
    @abstractmethod
    def update_status(self, asset_id: str, status: str) -> None:
        pass
