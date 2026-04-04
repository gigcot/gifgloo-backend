from dataclasses import dataclass

from urllib.parse import urlparse
from shared.exceptions import ValidationException



@dataclass(frozen=True)
class StorageUrl:
    value: str

    def __post_init__(self):
        self._validate_url(self.value)


    def _validate_url(self, url: str) -> None:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValidationException("유효하지 않은 URL입니다")