from dataclasses import dataclass
from enum import Enum


class SocialProvider(Enum):
    KAKAO  = "KAKAO"
    GOOGLE = "GOOGLE"


@dataclass(frozen=True)
class SocialAccount:
    provider: SocialProvider
    provider_id: str
