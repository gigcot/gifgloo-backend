from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from user.adapter.outbound.persistence.models import UserModel
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User, UserRole, UserStatus
from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount, SocialProvider


class SqlAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, user: User) -> None:
        existing = self._session.get(UserModel, user.id)
        if existing:
            existing.email = user.email.value if user.email else None
            existing.role = user.role.value
            existing.status = user.status.value
        else:
            self._session.add(UserModel(
                id=user.id,
                provider=user.social_account.provider.value,
                provider_id=user.social_account.provider_id,
                email=user.email.value if user.email else None,
                role=user.role.value,
                status=user.status.value,
                created_at=user.created_at,
            ))
        self._session.commit()

    def find_by_id(self, user_id: str) -> Optional[User]:
        model = self._session.get(UserModel, user_id)
        return self._to_domain(model) if model else None

    def find_by_social_account(self, social_account: SocialAccount) -> Optional[User]:
        model = (
            self._session.query(UserModel)
            .filter(
                and_(
                    UserModel.provider == social_account.provider.value,
                    UserModel.provider_id == social_account.provider_id,
                )
            )
            .first()
        )
        return self._to_domain(model) if model else None

    def _to_domain(self, model: UserModel) -> User:
        user = object.__new__(User)
        user.id = model.id
        user.social_account = SocialAccount(
            provider=SocialProvider(model.provider),
            provider_id=model.provider_id,
        )
        user.email = Email(model.email) if model.email else None
        user.role = UserRole(model.role)
        user.status = UserStatus(model.status)
        user.created_at = model.created_at
        return user
