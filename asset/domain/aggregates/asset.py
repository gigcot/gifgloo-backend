from enum import Enum
from asset.domain.value_objects.storage_url import StorageUrl

class AssetStatus(Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"

class AssetType(Enum):
    ANIMATED = "ANIMATED"
    STATIC = "STATIC"

class Asset:
    def __init__(
            self,
            id: str,
            user_id: str,
            asset_type: AssetType,
            storage_url: StorageUrl,
        ):
        self.user_id = user_id
        self.id = id
        self.type = asset_type
        self.status = AssetStatus.ACTIVE
        self.storage_url = storage_url
    
    def delete(self, user_id: str) -> ...:
        if user_id != self.user_id:
            raise PermissionError("자신의 자산만 삭제할 수 있습니다")
        if self.status != AssetStatus.ACTIVE:
            raise ValueError("이미 삭제된 자산입니다")
        self.status = AssetStatus.DELETED
    
    def is_available_for_composition(self) -> bool:
        return self.status == AssetStatus.ACTIVE
        
    