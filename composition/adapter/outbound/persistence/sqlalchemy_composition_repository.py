from typing import Optional

from sqlalchemy.orm import Session

from composition.application.ports.outbound.composition_repository import CompositionRepository
from composition.domain.aggregates.composition_job import CompositionJob


class SqlAlchemyCompositionRepository(CompositionRepository):
    def __init__(self, session: Session):
        self._session = session

    def save(self, job: CompositionJob) -> None:
        # TODO: ORM 매핑 모델로 변환 후 저장
        raise NotImplementedError

    def find_by_id(self, job_id: str) -> Optional[CompositionJob]:
        # TODO: ORM 매핑 모델 조회 후 도메인 객체로 변환
        raise NotImplementedError
