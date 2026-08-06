from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GetSharedAssetQuery:
    share_token: str


@dataclass
class GetSharedAssetResult:
    asset_id: str
    result_url: str


class GetSharedAssetPort(ABC):
    @abstractmethod
    def execute(self, query: GetSharedAssetQuery) -> GetSharedAssetResult:
        pass
