from datetime import datetime, timezone
from typing import Optional

from payment.domain.value_objects.payment_status import PaymentStatus
from payment.domain.value_objects.pg_type import PgType


class Payment:
    def __init__(
            self,
            user_id: str,
            pg_type: PgType,
            amount: int,
        ):
        self.user_id = user_id
        self.pg_type = pg_type
        self.amount = amount
        self.created_at: datetime = datetime.now(timezone.utc)
        self.status = PaymentStatus.PENDING
        self.failed_reason: Optional[str] = None

    def start(self):
        if self.status != PaymentStatus.PENDING:
            raise ValueError("대기 중인 결제만 처리 시작할 수 있습니다")
        self.status = PaymentStatus.PROCESSING

    def complete(self):
        if self.status != PaymentStatus.PROCESSING:
            raise ValueError("처리 중인 결제만 완료할 수 있습니다")
        self.status = PaymentStatus.COMPLETED
    
    def fail(self, failed_reason):
        self.status = PaymentStatus.FAILED
        self.failed_reason = failed_reason
    