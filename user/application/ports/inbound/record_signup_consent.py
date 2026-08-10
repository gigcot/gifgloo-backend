from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RecordSignupConsentCommand:
    user_id: str
    terms_version: str
    privacy_version: str
    is_fourteen_or_older: bool


@dataclass(frozen=True)
class RecordSignupConsentResult:
    terms_version: str
    privacy_version: str
    is_fourteen_or_older: bool
    agreed_at: datetime


class RecordSignupConsentPort(ABC):
    @abstractmethod
    def execute(self, command: RecordSignupConsentCommand) -> RecordSignupConsentResult:
        pass
