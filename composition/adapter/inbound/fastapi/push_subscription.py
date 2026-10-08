import base64
import binascii
import re
from urllib.parse import urlsplit
from cryptography.hazmat.primitives.asymmetric import ec
from shared.exceptions import ValidationException


def validate_push_subscription(endpoint: str, p256dh: str, auth: str) -> None:
    try:
        url = urlsplit(endpoint)
        host = url.hostname or ""
        allowed = host in ("fcm.googleapis.com", "updates.push.services.mozilla.com") or host.endswith((".push.apple.com", ".notify.windows.com"))
        if not allowed or url.scheme != "https" or url.port not in (None, 443) or url.username or url.password or url.fragment:
            raise ValidationException("지원하지 않는 알림 수신 주소입니다")
        for key in (p256dh, auth):
            if not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", key):
                raise ValidationException("알림 암호화 정보가 올바르지 않습니다")
        public_key = base64.urlsafe_b64decode(p256dh + "=" * (-len(p256dh) % 4))
        auth_bytes = base64.urlsafe_b64decode(auth + "=" * (-len(auth) % 4))
        if len(public_key) != 65 or len(auth_bytes) != 16:
            raise ValidationException("알림 암호화 정보가 올바르지 않습니다")
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public_key)
    except (ValueError, binascii.Error) as exc:
        raise ValidationException("알림 수신 정보가 올바르지 않습니다") from exc
