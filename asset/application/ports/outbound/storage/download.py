from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class StorageDownloadCommand:
    storage_url: str


@dataclass
class StorageDownloadResult:
    bytes: bytes


class StorageDownloadPort(ABC):
    @abstractmethod
    def execute(self, command: StorageDownloadCommand) -> StorageDownloadResult:
        pass
