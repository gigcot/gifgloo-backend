from enum import Enum


class PaymentEnvironment(Enum):
    UNKNOWN = "UNKNOWN"
    TEST = "TEST"
    LIVE = "LIVE"
