from enum import Enum


class TransactionType(Enum):
    CHARGE = "CHARGE"
    DEDUCT = "DEDUCT"
    REFUND = "REFUND"
