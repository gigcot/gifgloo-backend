from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

from user.domain.value_objects.email import Email
from user.domain.value_objects.social_account import SocialAccount
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
        social_account: SocialAccount,
        email: Optional[Email] = None,
        role: UserRole = UserRole.USER,
    ):
        self.id: str = str(uuid.uuid4())
        self.social_account: SocialAccount = social_account
        self.email: Optional[Email] = email
        self.role: UserRole = role
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

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE
