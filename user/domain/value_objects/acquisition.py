from dataclasses import dataclass

from shared.exceptions import BusinessRuleException


@dataclass(frozen=True)
class Acquisition:
    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    content: str | None = None

    def __post_init__(self):
        for value in (self.source, self.medium, self.campaign, self.content):
            if value is not None and (not value.strip() or len(value) > 100):
                raise BusinessRuleException("유입 정보는 1~100자여야 합니다")
