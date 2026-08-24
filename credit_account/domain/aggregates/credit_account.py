from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import uuid

from credit_account.domain.value_objects.credit_policy import CreditPolicy
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import BusinessRuleException, InsufficientCreditException, InvalidStateException


@dataclass
class CreditLot:
    granted_amount: int
    remaining_amount: int
    expires_at: datetime
    source_type: CreditSourceType | None = None
    source_id: str | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at <= now

    def available_amount(self, now: datetime) -> int:
        return 0 if self.is_expired(now) else self.remaining_amount


@dataclass
class CreditTransaction:
    amount: int
    transaction_type: TransactionType
    source_type: CreditSourceType | None = None
    source_id: str | None = None
    credit_lot_id: str | None = None
    reason: str | None = None
    balance_after: int | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CreditAccount:
    composition_cost = CreditPolicy.COMPOSITION_COST

    def __init__(
        self,
        user_id: str,
        balance: int,
        transactions: list[CreditTransaction],
        lots: list[CreditLot] | None = None,
    ):
        self.user_id = user_id
        self.balance = balance
        self.transactions = transactions
        self.lots = lots or []
        self._pending_transactions: list[CreditTransaction] = []
        self._pending_lots: list[CreditLot] = []
        self._changed_lot_ids: set[str] = set()

    @property
    def pending_transactions(self) -> tuple[CreditTransaction, ...]:
        return tuple(self._pending_transactions)

    @property
    def pending_lots(self) -> tuple[CreditLot, ...]:
        return tuple(self._pending_lots)

    @property
    def changed_lot_ids(self) -> frozenset[str]:
        return frozenset(self._changed_lot_ids)

    def mark_pending_changes_persisted(self) -> None:
        self._pending_transactions.clear()
        self._pending_lots.clear()
        self._changed_lot_ids.clear()

    def mark_pending_transactions_persisted(self) -> None:
        self.mark_pending_changes_persisted()

    def available_balance(self, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        return sum(lot.available_amount(current) for lot in self.lots)

    def nearest_expiration(self, now: datetime | None = None) -> datetime | None:
        current = now or datetime.now(timezone.utc)
        expirations = [
            lot.expires_at
            for lot in self.lots
            if lot.available_amount(current) > 0
        ]
        return min(expirations) if expirations else None

    def has_enough(self, now: datetime | None = None) -> bool:
        return self.available_balance(now) >= self.composition_cost

    def _expire_lots(self, now: datetime) -> None:
        for lot in self.lots:
            if lot.remaining_amount == 0 or not lot.is_expired(now):
                continue
            expired_amount = lot.remaining_amount
            lot.remaining_amount = 0
            self.balance -= expired_amount
            self._changed_lot_ids.add(lot.id)
            self._record_transaction(
                amount=expired_amount,
                transaction_type=TransactionType.EXPIRATION,
                source_type=CreditSourceType.LOT,
                source_id=lot.id,
                credit_lot_id=lot.id,
                reason="이용권 사용기한 만료",
                created_at=lot.expires_at,
            )

    def deduct(
        self,
        source_type: CreditSourceType | None = None,
        source_id: str | None = None,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        self._validate_source(source_type, source_id)
        self._expire_lots(current)
        lot = next(
            (
                candidate
                for candidate in sorted(self.lots, key=lambda item: item.expires_at)
                if not candidate.is_expired(current)
                and candidate.remaining_amount >= self.composition_cost
            ),
            None,
        )
        if lot is None:
            raise InsufficientCreditException("사용 가능한 GIF 합성 이용권이 없습니다")

        lot.remaining_amount -= self.composition_cost
        self.balance -= self.composition_cost
        self._changed_lot_ids.add(lot.id)
        self._record_transaction(
            amount=self.composition_cost,
            transaction_type=TransactionType.DEDUCT,
            source_type=source_type,
            source_id=source_id,
            credit_lot_id=lot.id,
            created_at=current,
        )

    def refund(
        self,
        original_lot_id: str,
        source_type: CreditSourceType | None = None,
        source_id: str | None = None,
        now: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        self._validate_source(source_type, source_id)
        self._expire_lots(current)
        original_lot = next(
            (lot for lot in self.lots if lot.id == original_lot_id),
            None,
        )
        if original_lot is None:
            raise InvalidStateException("차감에 사용된 이용권을 찾을 수 없습니다")

        expired = original_lot.is_expired(current)
        if expired:
            restored_lot = CreditLot(
                granted_amount=self.composition_cost,
                remaining_amount=self.composition_cost,
                expires_at=current + timedelta(days=CreditPolicy.COMPENSATION_VALIDITY_DAYS),
                source_type=source_type,
                source_id=source_id,
                created_at=current,
            )
            self.lots.append(restored_lot)
            self._pending_lots.append(restored_lot)
        else:
            if original_lot.remaining_amount + self.composition_cost > original_lot.granted_amount:
                raise InvalidStateException("이용권 복구 가능량을 초과했습니다")
            original_lot.remaining_amount += self.composition_cost
            self._changed_lot_ids.add(original_lot.id)
            restored_lot = original_lot

        self.balance += self.composition_cost
        self._record_transaction(
            amount=self.composition_cost,
            transaction_type=TransactionType.REFUND,
            source_type=source_type,
            source_id=source_id,
            credit_lot_id=restored_lot.id,
            reason=(
                "만료 후 합성 실패 24시간 보상"
                if expired
                else "합성 실패 이용권 복구"
            ),
            created_at=current,
        )

    def charge(
        self,
        amount: int,
        source_type: CreditSourceType | None = None,
        source_id: str | None = None,
        reason: str | None = None,
        granted_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> CreditLot:
        if amount <= 0 or amount % self.composition_cost != 0:
            raise BusinessRuleException("이용권 지급량은 합성 비용의 양의 배수여야 합니다")
        self._validate_source(source_type, source_id)
        current = datetime.now(timezone.utc)
        self._expire_lots(current)
        created_at = granted_at or current
        expiration = expires_at or (
            created_at + timedelta(days=CreditPolicy.PASS_VALIDITY_DAYS)
        )
        if expiration <= created_at:
            raise BusinessRuleException("이용권 만료일은 지급 시점 이후여야 합니다")

        lot = CreditLot(
            granted_amount=amount,
            remaining_amount=amount,
            expires_at=expiration,
            source_type=source_type,
            source_id=source_id,
            created_at=created_at,
        )
        self.lots.append(lot)
        self._pending_lots.append(lot)
        self.balance += amount
        self._record_transaction(
            amount=amount,
            transaction_type=TransactionType.CHARGE,
            source_type=source_type,
            source_id=source_id,
            credit_lot_id=lot.id,
            reason=reason,
            created_at=created_at,
        )
        return lot

    @staticmethod
    def _validate_source(
        source_type: CreditSourceType | None,
        source_id: str | None,
    ) -> None:
        if (source_type is None) != (source_id is None):
            raise BusinessRuleException("크레딧 출처 종류와 식별자는 함께 지정해야 합니다")

    def _record_transaction(
        self,
        amount: int,
        transaction_type: TransactionType,
        source_type: CreditSourceType | None,
        source_id: str | None,
        credit_lot_id: str,
        created_at: datetime,
        reason: str | None = None,
    ) -> None:
        transaction = CreditTransaction(
            amount=amount,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            credit_lot_id=credit_lot_id,
            reason=reason,
            balance_after=self.balance,
            created_at=created_at,
        )
        self.transactions.append(transaction)
        self._pending_transactions.append(transaction)
