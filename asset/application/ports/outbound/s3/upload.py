from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class UploadToS3Command:
    asset_id: str
    asset_type: str
    image_data: bytes

@dataclass
class UploadToS3Result:
    storage_url: str

class UploadToS3Port(ABC):
    @abstractmethod
    def execute(self, command: UploadToS3Command) -> UploadToS3Result:
        pass

