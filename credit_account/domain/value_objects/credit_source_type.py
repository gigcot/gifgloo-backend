from enum import Enum


class CreditSourceType(Enum):
    PAYMENT = "PAYMENT"
    ADMIN = "ADMIN"
    COMPOSITION = "COMPOSITION"
    LOT = "LOT"
