from dataclasses import dataclass
from datetime import datetime, timezone

from shared.exceptions import BusinessRuleException


CURRENT_TERMS_VERSION = "2026-08-09"
CURRENT_PRIVACY_VERSION = "2026-08-09"


@dataclass(frozen=True)
class SignupConsent:
    terms_version: str
    privacy_version: str
    is_fourteen_or_older: bool
    agreed_at: datetime

    @classmethod
    def record(
        cls,
        terms_version: str,
        privacy_version: str,
        is_fourteen_or_older: bool,
    ) -> "SignupConsent":
        if terms_version != CURRENT_TERMS_VERSION:
            raise BusinessRuleException("현재 이용약관에 동의해야 합니다")
        if privacy_version != CURRENT_PRIVACY_VERSION:
            raise BusinessRuleException("현재 개인정보처리방침에 동의해야 합니다")
        if not is_fourteen_or_older:
            raise BusinessRuleException("만 14세 이상만 가입할 수 있습니다")

        return cls(
            terms_version=terms_version,
            privacy_version=privacy_version,
            is_fourteen_or_older=True,
            agreed_at=datetime.now(timezone.utc),
        )
