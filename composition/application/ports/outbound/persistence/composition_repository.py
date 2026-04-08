from abc import ABC, abstractmethod
from typing import Optional

from composition.domain.aggregates.composition_job import CompositionJob


class CompositionRepository(ABC):
    @abstractmethod
    def save(self, job: CompositionJob) -> None:
        pass

    @abstractmethod
    def find_by_id(self, job_id: str) -> Optional[CompositionJob]:
        pass

    @abstractmethod
    def find_all_processing(self) -> list[CompositionJob]:
        """status=PROCESSING이고 gif_url이 있는 job 목록 (재시작 복구용)"""
        pass

    @abstractmethod
    def find_all_by_user_id(self, user_id: str) -> list[CompositionJob]:
        pass
