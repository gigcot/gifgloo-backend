from enum import Enum


class PaymentProvider(Enum):
    KG_INICIS = "KG_INICIS"
    TOSS_PAY = "TOSS_PAY"
    TOSS_PAYMENTS = "TOSS_PAYMENTS"
    KAKAO_PAY = "KAKAO_PAY"
