from dataclasses import dataclass
from enum import Enum

class AssetCategory(Enum):
    KLIPY_GIF = "KLIPY_GIF"
    USER_UPLOAD = "USER_UPLOAD"
    COMPOSITION_DRAFT = "COMPOSITION_DRAFT"
    COMPOSITION_RESULT = "COMPOSITION_RESULT"

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
