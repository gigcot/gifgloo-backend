import os

from shared.exceptions import ExternalServiceException
from payment.domain.value_objects.payment_environment import PaymentEnvironment


PAYMENT_REQUIRED_ENV_NAMES = (
    "PORTONE_API_SECRET",
    "PORTONE_EXPECTED_CHANNEL_TYPE",
)


def required_payment_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise ExternalServiceException(f"{name} 환경변수가 설정되지 않았습니다")
    return value


def required_portone_environment() -> PaymentEnvironment:
    value = required_payment_env("PORTONE_EXPECTED_CHANNEL_TYPE")
    try:
        environment = PaymentEnvironment(value)
    except ValueError as exc:
        raise ExternalServiceException(
            "PORTONE_EXPECTED_CHANNEL_TYPE은 TEST 또는 LIVE여야 합니다"
        ) from exc
    if environment == PaymentEnvironment.UNKNOWN:
        raise ExternalServiceException(
            "PORTONE_EXPECTED_CHANNEL_TYPE은 TEST 또는 LIVE여야 합니다"
        )
    return environment


def validate_payment_config() -> None:
    if os.getenv("APP_ENV", "development") != "production":
        return

    for name in PAYMENT_REQUIRED_ENV_NAMES:
        required_payment_env(name)
    required_portone_environment()
