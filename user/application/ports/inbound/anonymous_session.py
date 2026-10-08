from dataclasses import dataclass

from user.domain.value_objects.acquisition import Acquisition


@dataclass
class AnonymousSessionCommand:
    user_id: str
    acquisition: Acquisition | None = None


@dataclass
class AnonymousSessionResult:
    user_id: str
    created: bool
    session_version: int
