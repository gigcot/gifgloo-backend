from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StorageUploadCommand:
    asset_id: str
    asset_type: str
    image_data: bytes


@dataclass
class StorageUploadResult:
    storage_url: str


class StorageUploadPort(ABC):
    @abstractmethod
    def execute(self, command: StorageUploadCommand) -> StorageUploadResult:
        pass
