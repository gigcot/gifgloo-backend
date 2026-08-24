import base64
import binascii
import json
from dataclasses import dataclass
from datetime import datetime
from json import JSONDecodeError

from shared.exceptions import ValidationException


@dataclass(frozen=True)
class PageCursor:
    created_at: datetime
    item_id: str


def encode_page_cursor(created_at: datetime, item_id: str) -> str:
    payload = json.dumps(
        {"created_at": created_at.isoformat(), "id": item_id},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_page_cursor(cursor: str) -> PageCursor:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        created_at = datetime.fromisoformat(payload["created_at"])
        item_id = payload["id"]
    except (
        binascii.Error,
        JSONDecodeError,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ):
        raise ValidationException("유효하지 않은 페이지 커서입니다")
    if created_at.utcoffset() is None or not isinstance(item_id, str) or not item_id:
        raise ValidationException("유효하지 않은 페이지 커서입니다")
    return PageCursor(created_at=created_at, item_id=item_id)
