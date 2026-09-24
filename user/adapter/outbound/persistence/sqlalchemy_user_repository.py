from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from user.adapter.outbound.persistence.models import UserModel
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User, UserRole, UserStatus
from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount, SocialProvider
from user.domain.value_objects.signup_consent import SignupConsent
from user.domain.value_objects.acquisition import Acquisition


class SqlAlchemyUserRepository(UserRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, user: User) -> None:
        existing = self._session.get(UserModel, user.id)
        if existing:
            existing.email = user.email.value if user.email else None
            existing.role = user.role.value
            existing.status = user.status.value
            existing.terms_version = (
                user.signup_consent.terms_version if user.signup_consent else None
            )
            existing.privacy_version = (
                user.signup_consent.privacy_version if user.signup_consent else None
            )
            existing.is_fourteen_or_older = bool(
                user.signup_consent and user.signup_consent.is_fourteen_or_older
            )
            existing.consented_at = (
                user.signup_consent.agreed_at if user.signup_consent else None
            )
        else:
            self._session.add(UserModel(
                id=user.id,
                provider=user.social_account.provider.value,
                provider_id=user.social_account.provider_id,
                email=user.email.value if user.email else None,
                role=user.role.value,
                status=user.status.value,
                created_at=user.created_at,
                acquisition_source=user.acquisition.source if user.acquisition else None,
                acquisition_medium=user.acquisition.medium if user.acquisition else None,
                acquisition_campaign=user.acquisition.campaign if user.acquisition else None,
                acquisition_content=user.acquisition.content if user.acquisition else None,
                terms_version=(
                    user.signup_consent.terms_version if user.signup_consent else None
                ),
                privacy_version=(
                    user.signup_consent.privacy_version if user.signup_consent else None
                ),
                is_fourteen_or_older=bool(
                    user.signup_consent and user.signup_consent.is_fourteen_or_older
                ),
                consented_at=(
                    user.signup_consent.agreed_at if user.signup_consent else None
                ),
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
        user.acquisition = Acquisition(
            source=model.acquisition_source,
            medium=model.acquisition_medium,
            campaign=model.acquisition_campaign,
            content=model.acquisition_content,
        ) if any((model.acquisition_source, model.acquisition_medium, model.acquisition_campaign, model.acquisition_content)) else None
        user.signup_consent = (
            SignupConsent(
                terms_version=model.terms_version,
                privacy_version=model.privacy_version,
                is_fourteen_or_older=model.is_fourteen_or_older,
                agreed_at=model.consented_at,
            )
            if model.consented_at
            else None
        )
        return user
