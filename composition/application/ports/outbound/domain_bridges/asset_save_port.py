from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AssetSaveCommand:
    user_id: str
    category: str
    url: Optional[str] = None
    image_data: Optional[bytes] = None


class AssetSavePort(ABC):
    @abstractmethod
    def save(self, command: AssetSaveCommand) -> str:
        """저장 후 asset_id 반환"""
        pass
