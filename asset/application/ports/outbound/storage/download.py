from abc import ABC, abstractmethod
from dataclasses import dataclass
from shared.asset_category import AssetCategory


@dataclass
class StorageDownloadCommand:
    storage_url: str
    category: AssetCategory


@dataclass
class StorageDownloadResult:
    bytes: bytes
    content_type: str


class StorageDownloadPort(ABC):
    @abstractmethod
    def execute(self, command: StorageDownloadCommand) -> StorageDownloadResult:
        pass
