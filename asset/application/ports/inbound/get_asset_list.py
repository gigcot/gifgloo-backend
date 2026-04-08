
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from asset.application.dto import AssetDto
from shared.asset_category import AssetCategory


@dataclass
class GetAssetListCommand:
    user_id: str
    category: Optional[AssetCategory] = None

@dataclass
class GetAssetListResult:
    assets: list[AssetDto]

class GetAssetListPort(ABC):
    @abstractmethod
    def execute(self, command: GetAssetListCommand) -> GetAssetListResult:
        pass