from abc import ABC, abstractmethod
from enum import Enum


class StorageCategory(Enum):
    TARGET = "target"
    DRAFT = "draft"
    RESULT = "result"


class StoragePort(ABC):
    @abstractmethod
    async def upload(self, job_id: str, category: StorageCategory, data: bytes) -> str:
        """업로드 후 R2 key 반환"""
        pass

    @abstractmethod
    def make_key(self, job_id: str, category: StorageCategory) -> str:
        """업로드 없이 key만 생성 (Lambda가 직접 저장할 때 사용)"""
        pass

    @abstractmethod
    def location_for(self, key: str, category: StorageCategory) -> str:
        """공개 결과 URL 또는 서버 내부 비공개 파일 위치 반환"""
        pass
