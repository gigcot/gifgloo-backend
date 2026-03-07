from dataclasses import dataclass
from enum import Enum

@dataclass
class AssetCategory(Enum):
    EXTERNAL = "EXETERNAL"
    INTERNAL = "INTERNAL"

@dataclass
class AssetDto:
    asset_id: str
    asset_type: str
    category: AssetCategory
    url: str

@dataclass
class AssetResult:
    id: str
    user_id: str
    asset_type: str
    storage_url: str
