from enum import Enum


class PaymentProvider(Enum):
    TOSS_PAY = "TOSS_PAY"
    TOSS_PAYMENTS = "TOSS_PAYMENTS"
    KAKAO_PAY = "KAKAO_PAY"
