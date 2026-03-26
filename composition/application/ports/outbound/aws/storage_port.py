from abc import ABC, abstractmethod


class StoragePort(ABC):
    @abstractmethod
    async def upload(self, job_id: str, category: str, data: bytes) -> str:
        """업로드 후 public URL 반환.

        category: "target", "draft", "result" 등 용도 구분
        """
        pass
