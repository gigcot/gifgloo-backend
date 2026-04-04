from dataclasses import dataclass

from shared.asset_category import AssetCategory
from asset.domain.aggregates.asset import AssetType


@dataclass
class AssetDto:
    asset_id: str
    asset_type: AssetType
    category: AssetCategory
    url: str


@dataclass
class AssetResult:
    id: str
    user_id: str
    asset_type: AssetType
    storage_url: str
