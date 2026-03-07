from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DownloadfromS3Command:
    storage_url: str

@dataclass
class DownloadfromS3Result:
    bytes: bytes

class DownloadfromS3Port(ABC):
    @abstractmethod
    def execute(self, command: DownloadfromS3Command) -> DownloadfromS3Result:
        pass

