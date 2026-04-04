from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from credit_account.adapter.outbound.sql_alchemy_credit_account_repository import SqlAlchemyCreditAccountRepository
from credit_account.application.services.create_credit_account_service import CreateCreditAccountService
from user.adapter.outbound.domain_bridges.credit_account_init_adapter import CreditAccountInitAdapter
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.adapter.outbound.social.kakao_social_provider_adapter import KakaoSocialProviderAdapter
from user.adapter.outbound.social.google_social_provider_adapter import GoogleSocialProviderAdapter
from user.application.services.social_login_service import SocialLoginService


def _make_social_login_service(provider, db: Session) -> SocialLoginService:
    credit_repo = SqlAlchemyCreditAccountRepository(db)
    credit_init = CreditAccountInitAdapter(CreateCreditAccountService(credit_repo))
    return SocialLoginService(
        social_provider=provider,
        user_repo=SqlAlchemyUserRepository(db),
        credit_account_init=credit_init,
    )


def get_kakao_social_login_service(db: Session = Depends(get_db)) -> SocialLoginService:
    return _make_social_login_service(KakaoSocialProviderAdapter(), db)


def get_google_social_login_service(db: Session = Depends(get_db)) -> SocialLoginService:
    return _make_social_login_service(GoogleSocialProviderAdapter(), db)
