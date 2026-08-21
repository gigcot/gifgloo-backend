import os

from config.payment_settings import required_payment_env
from payment.adapter.outbound.payment_gateway.portone_http_adapter import (
    PortOneHttpAdapter,
)
from payment.adapter.outbound.payment_gateway.toss_pay_http_adapter import (
    TossPayHttpAdapter,
)


def make_toss_pay_gateway() -> TossPayHttpAdapter:
    return TossPayHttpAdapter(
        api_key=required_payment_env("TOSS_PAY_API_KEY"),
        result_callback_url=required_payment_env("TOSS_PAY_RESULT_CALLBACK_URL"),
        return_url=required_payment_env("TOSS_PAY_RETURN_URL"),
        cancel_url=required_payment_env("TOSS_PAY_CANCEL_URL"),
        base_url=os.getenv("TOSS_PAY_BASE_URL", "https://pay.toss.im/api/v2"),
    )


def make_portone_gateway() -> PortOneHttpAdapter:
    return PortOneHttpAdapter(
        api_secret=required_payment_env("PORTONE_API_SECRET"),
        base_url=os.getenv("PORTONE_API_BASE_URL", "https://api.portone.io"),
    )
