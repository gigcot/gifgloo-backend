from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PrepareUploadCommand:
    user_id: str
    content_type: str
    size: int


@dataclass(frozen=True)
class PrepareUploadResult:
    upload_id: str
    upload_url: str
    headers: dict[str, str]
    expires_in_seconds: int


@dataclass(frozen=True)
class ResolveUploadCommand:
    user_id: str
    upload_id: str


class UploadStagingPort(ABC):
    @abstractmethod
    async def prepare(self, command: PrepareUploadCommand) -> PrepareUploadResult:
        pass

    @abstractmethod
    async def resolve(self, command: ResolveUploadCommand) -> str:
        pass
