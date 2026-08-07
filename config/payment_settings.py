import os

from shared.exceptions import ExternalServiceException


TOSS_PAY_REQUIRED_ENV_NAMES = (
    "TOSS_PAY_API_KEY",
    "TOSS_PAY_RESULT_CALLBACK_URL",
    "TOSS_PAY_RETURN_URL",
    "TOSS_PAY_CANCEL_URL",
)


def required_payment_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise ExternalServiceException(f"{name} 환경변수가 설정되지 않았습니다")
    return value


def validate_payment_config() -> None:
    if os.getenv("APP_ENV", "development") != "production":
        return

    for name in TOSS_PAY_REQUIRED_ENV_NAMES:
        required_payment_env(name)

    api_key = required_payment_env("TOSS_PAY_API_KEY")
    if api_key.startswith("sk_test_"):
        raise ExternalServiceException("운영 환경에서 토스페이 테스트 키를 사용할 수 없습니다")
