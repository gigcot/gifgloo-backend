from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GetAssetUrlCommand:
    user_id: str
    asset_id: str

@dataclass
class GetAssetUrlResult:
    url: str

class GetAssetUrlPort(ABC):
    @abstractmethod
    def execute(self, command: GetAssetUrlCommand) -> GetAssetUrlResult:
        pass