from dataclasses import dataclass

from asset.domain.aggregates.asset import AssetType
from shared.asset_category import AssetCategory


@dataclass(frozen=True)
class AssetListItem:
    asset_id: str
    asset_type: AssetType
    category: AssetCategory
    url: str
