from sqlalchemy.ext.asyncio import AsyncSession

from user.adapter.outbound.persistence.models import UserModel
from user.application.ports.outbound.async_user_repository import AsyncUserRepository
from user.domain.aggregates.user import User, UserRole, UserStatus
from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount, SocialProvider
from user.domain.value_objects.signup_consent import SignupConsent


class SqlAlchemyAsyncUserRepository(AsyncUserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_id(self, user_id: str) -> User | None:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            return None
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
