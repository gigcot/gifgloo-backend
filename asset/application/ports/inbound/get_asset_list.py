
from abc import ABC, abstractmethod
from dataclasses import dataclass

from asset.application.dto import AssetDto


@dataclass
class GetAssetListCommand:
    user_id: str

@dataclass
class GetAssetListResult:
    assets: list[AssetDto]

class GetAssetListPort(ABC):
    @abstractmethod
    def execute(self, command: GetAssetListCommand) -> GetAssetListResult:
        pass