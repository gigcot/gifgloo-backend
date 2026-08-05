from enum import Enum


class PaymentStatus(Enum):
    READY = "READY"
    AUTHORIZED = "AUTHORIZED"
    APPROVED = "APPROVED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"

    PENDING = "READY"
    PROCESSING = "AUTHORIZED"
    COMPLETED = "APPROVED"
