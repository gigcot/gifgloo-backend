from typing import Optional

from sqlalchemy.orm import Session

from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User
from user.domain.value_objects.social_account import SocialAccount


class SqlAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, user: User) -> None:
        # TODO: ORM 매핑 모델로 변환 후 저장
        raise NotImplementedError

    def find_by_id(self, user_id: str) -> Optional[User]:
        # TODO: ORM 매핑 모델 조회 후 도메인 객체로 변환
        raise NotImplementedError

    def find_by_social_account(self, social_account: SocialAccount) -> Optional[User]:
        # TODO: provider + provider_id 로 조회
        raise NotImplementedError
