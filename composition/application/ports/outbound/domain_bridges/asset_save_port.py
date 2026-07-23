from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from shared.asset_category import AssetCategory


@dataclass
class AssetSaveCommand:
    user_id: str
    category: AssetCategory
    url: Optional[str] = None
    image_data: Optional[bytes] = None


class AssetSavePort(ABC):
    @abstractmethod
    async def save(self, command: AssetSaveCommand) -> str:
        pass
