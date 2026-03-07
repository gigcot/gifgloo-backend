from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from asset.application.dto import AssetDto

@dataclass
class SaveAssetCommand:
    user_id: str
    category: str
    asset_type: str
    url: str
    image_data: Optional[bytes]

class SaveAssetPort(ABC):
    @abstractmethod
    def execute(self, command: SaveAssetCommand) -> None:
        pass