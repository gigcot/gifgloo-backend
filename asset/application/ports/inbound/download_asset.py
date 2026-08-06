from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DownloadAssetCommand:
    user_id: str
    asset_id: str


@dataclass
class DownloadSharedAssetQuery:
    share_token: str


@dataclass
class DownloadAssetResult:
    data: bytes


class DownloadAssetPort(ABC):
    @abstractmethod
    def execute(self, command: DownloadAssetCommand) -> DownloadAssetResult:
        pass


class DownloadSharedAssetPort(ABC):
    @abstractmethod
    def execute(self, query: DownloadSharedAssetQuery) -> DownloadAssetResult:
        pass
