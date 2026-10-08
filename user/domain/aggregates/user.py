from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount
from user.domain.value_objects.signup_consent import SignupConsent, CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION
from user.domain.value_objects.acquisition import Acquisition
from shared.exceptions import InvalidStateException


class UserRole(Enum):
    USER  = "USER"
    ADMIN = "ADMIN"


class UserStatus(Enum):
    ACTIVE   = "ACTIVE"
    INACTIVE = "INACTIVE"


class User:
    def __init__(
        self,
        social_account: SocialAccount | None = None,
        email: Optional[Email] = None,
        role: UserRole = UserRole.USER,
        signup_consent: Optional[SignupConsent] = None,
        acquisition: Acquisition | None = None,
    ):
        self.id: str = str(uuid.uuid4())
        self.social_account = social_account
        self.session_version = 0
        self.email: Optional[Email] = email
        self.role: UserRole = role
        self.signup_consent: Optional[SignupConsent] = signup_consent
        self.acquisition = acquisition
        self.status: UserStatus = UserStatus.ACTIVE
        self.created_at: datetime = datetime.now(timezone.utc)

    def deactivate(self) -> None:
        if self.status == UserStatus.INACTIVE:
            raise InvalidStateException("이미 탈퇴한 유저입니다")
        self.status = UserStatus.INACTIVE

    def change_role(self, role: UserRole) -> None:
        # 여기에 뭔가 권한 체크 로직이 있어야할거같기도
        # 이 요청 전에 이 걸할수있는 권한을 체크한다던가
        self.role = role

    def update_email(self, email: Email) -> None:
        self.email = email

    def record_signup_consent(
        self,
        terms_version: str,
        privacy_version: str,
        is_fourteen_or_older: bool,
    ) -> None:
        if (
            self.signup_consent
            and self.signup_consent.terms_version == terms_version
            and self.signup_consent.privacy_version == privacy_version
            and self.signup_consent.is_fourteen_or_older == is_fourteen_or_older
        ):
            return
        self.signup_consent = SignupConsent.record(
            terms_version=terms_version,
            privacy_version=privacy_version,
            is_fourteen_or_older=is_fourteen_or_older,
        )

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def user_kind(self) -> str:
        return "member" if self.social_account is not None else "anonymous"

    @property
    def consent_required(self) -> bool:
        return (
            self.signup_consent is None
            or self.signup_consent.terms_version != CURRENT_TERMS_VERSION
            or self.signup_consent.privacy_version != CURRENT_PRIVACY_VERSION
        )

    def connect_social_account(self, account: SocialAccount, email: Email | None) -> None:
        if self.social_account is not None or not self.is_active():
            raise InvalidStateException("소셜 계정을 연결할 수 없는 사용자입니다")
        self.social_account = account
        self.email = email
        self.session_version += 1
