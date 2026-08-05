from __future__ import annotations

from datetime import datetime, timezone
import uuid

from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_status import PaymentStatus
from payment.domain.value_objects.pg_type import PgType
from shared.exceptions import BusinessRuleException, InvalidStateException


class Payment:
    def __init__(
        self,
        user_id: str,
        provider: PaymentProvider | PgType,
        amount: int,
        credit_amount: int,
        order_id: str | None = None,
        currency: str = "KRW",
    ):
        if amount <= 0:
            raise BusinessRuleException("결제 금액은 0보다 커야 합니다")
        if credit_amount <= 0:
            raise BusinessRuleException("지급 크레딧은 0보다 커야 합니다")

        self.id: str = str(uuid.uuid4())
        self.user_id = user_id
        self.provider = self._normalize_provider(provider)
        self.pg_type = PgType(self.provider.value)
        self.order_id = order_id or f"gifgloo_{uuid.uuid4().hex}"
        self.amount = amount
        self.currency = currency
        self.credit_amount = credit_amount
        self.provider_payment_id: str | None = None
        self.provider_transaction_id: str | None = None
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = self.created_at
        self.authorized_at: datetime | None = None
        self.approved_at: datetime | None = None
        self.canceled_at: datetime | None = None
        self.credit_granted_at: datetime | None = None
        self.status = PaymentStatus.READY
        self.failed_reason: str | None = None
        self.cancel_reason: str | None = None

    @staticmethod
    def _normalize_provider(provider: PaymentProvider | PgType) -> PaymentProvider:
        return PaymentProvider(provider.value)

    def assign_provider_payment(
        self,
        provider_payment_id: str,
        provider_transaction_id: str | None = None,
    ) -> None:
        if self.provider_payment_id and self.provider_payment_id != provider_payment_id:
            raise InvalidStateException("이미 다른 결제 식별자가 연결되어 있습니다")
        if (
            provider_transaction_id is not None
            and self.provider_transaction_id is not None
            and self.provider_transaction_id != provider_transaction_id
        ):
            raise InvalidStateException("이미 다른 결제 거래 식별자가 연결되어 있습니다")
        self.provider_payment_id = provider_payment_id
        if provider_transaction_id is not None:
            self.provider_transaction_id = provider_transaction_id
        self._touch()

    def authorize(
        self,
        provider_payment_id: str | None = None,
        provider_transaction_id: str | None = None,
        authorized_at: datetime | None = None,
    ) -> None:
        if provider_payment_id is not None:
            self.assign_provider_payment(provider_payment_id, provider_transaction_id)
        if self.status == PaymentStatus.AUTHORIZED:
            return
        if self.status != PaymentStatus.READY:
            raise InvalidStateException("준비 중인 결제만 승인 대기 상태로 변경할 수 있습니다")
        self.status = PaymentStatus.AUTHORIZED
        self.authorized_at = authorized_at or datetime.now(timezone.utc)
        self._touch()

    def approve(
        self,
        provider_payment_id: str | None = None,
        provider_transaction_id: str | None = None,
        approved_at: datetime | None = None,
    ) -> None:
        if provider_payment_id is not None:
            self.assign_provider_payment(provider_payment_id, provider_transaction_id)
        if self.status == PaymentStatus.APPROVED:
            return
        if self.status not in (PaymentStatus.READY, PaymentStatus.AUTHORIZED):
            raise InvalidStateException("준비 또는 승인 대기 중인 결제만 완료할 수 있습니다")
        self.status = PaymentStatus.APPROVED
        self.approved_at = approved_at or datetime.now(timezone.utc)
        self._touch()

    def validate_approval(
        self,
        provider: PaymentProvider,
        amount: int,
        currency: str,
    ) -> None:
        if self.provider != provider:
            raise BusinessRuleException("주문의 결제 제공자가 일치하지 않습니다")
        if self.amount != amount:
            raise BusinessRuleException("주문의 결제 금액이 일치하지 않습니다")
        if self.currency != currency:
            raise BusinessRuleException("주문의 결제 통화가 일치하지 않습니다")

    def cancel(self, reason: str, canceled_at: datetime | None = None) -> None:
        if self.status == PaymentStatus.CANCELED:
            return
        if self.status != PaymentStatus.APPROVED:
            raise InvalidStateException("완료된 결제만 취소할 수 있습니다")
        self.status = PaymentStatus.CANCELED
        self.canceled_at = canceled_at or datetime.now(timezone.utc)
        self.cancel_reason = reason
        self._touch()

    def fail(self, failed_reason: str) -> None:
        if self.status in (PaymentStatus.APPROVED, PaymentStatus.CANCELED):
            raise InvalidStateException("완료 또는 취소된 결제는 실패 처리할 수 없습니다")
        self.status = PaymentStatus.FAILED
        self.failed_reason = failed_reason
        self._touch()

    def mark_credit_granted(self, granted_at: datetime | None = None) -> None:
        if self.status != PaymentStatus.APPROVED:
            raise InvalidStateException("완료된 결제만 크레딧 지급 처리할 수 있습니다")
        if self.credit_granted_at is not None:
            return
        self.credit_granted_at = granted_at or datetime.now(timezone.utc)
        self._touch()

    def can_grant_credit(self) -> bool:
        return self.status == PaymentStatus.APPROVED and self.credit_granted_at is None

    def start(self) -> None:
        self.authorize()

    def complete(self) -> None:
        self.approve()

    def _touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
