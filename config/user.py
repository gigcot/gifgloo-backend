import os

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
from user.application.services.get_user_service import GetUserService
from user.application.services.record_signup_consent_service import RecordSignupConsentService
from user.application.services.review_login_service import ReviewLoginService


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


def get_record_signup_consent_service(
    db: Session = Depends(get_db),
) -> RecordSignupConsentService:
    return RecordSignupConsentService(SqlAlchemyUserRepository(db))


def get_user_service(db: Session = Depends(get_db)) -> GetUserService:
    return GetUserService(SqlAlchemyUserRepository(db))


def get_review_login_service(db: Session = Depends(get_db)) -> ReviewLoginService:
    enabled = os.getenv("PG_REVIEW_LOGIN_ENABLED", "false").lower() == "true"
    login_id = os.environ["PG_REVIEW_LOGIN_ID"] if enabled else ""
    password_hash = os.environ["PG_REVIEW_PASSWORD_HASH"] if enabled else ""
    credit_repo = SqlAlchemyCreditAccountRepository(db)
    credit_init = CreditAccountInitAdapter(CreateCreditAccountService(credit_repo))
    return ReviewLoginService(
        enabled=enabled,
        login_id=login_id,
        password_hash=password_hash,
        user_repo=SqlAlchemyUserRepository(db),
        credit_account_init=credit_init,
    )
