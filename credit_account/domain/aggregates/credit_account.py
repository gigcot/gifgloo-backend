from dataclasses import dataclass, field
from datetime import datetime, timezone
from credit_account.domain.value_objects.credit_policy import CreditPolicy
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import BusinessRuleException
import uuid


@dataclass
class CreditTransaction:
    amount: int
    transaction_type: TransactionType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class CreditAccount:
    composition_cost = CreditPolicy.COMPOSITION_COST

    def __init__(
            self,
            user_id: str,
            balance: int,
            transactions: list[CreditTransaction],
    ):
        self.user_id = user_id
        self.balance = balance
        self.transactions = transactions
        self._pending_transactions: list[CreditTransaction] = []

    @property
    def pending_transactions(self) -> tuple[CreditTransaction, ...]:
        return tuple(self._pending_transactions)

    def mark_pending_transactions_persisted(self) -> None:
        self._pending_transactions.clear()

    def has_enough(self) -> bool:
        return self.balance >= self.composition_cost

    def deduct(self) -> None:
        if not self.has_enough():
            raise BusinessRuleException("잔액이 충분하지 않습니다")
        self.balance -= self.composition_cost
        transaction = CreditTransaction(
            amount=self.composition_cost,
            transaction_type=TransactionType.DEDUCT,
        )
        self.transactions.append(transaction)
        self._pending_transactions.append(transaction)

    def refund(self) -> None:
        self.balance += self.composition_cost
        transaction = CreditTransaction(
            amount=self.composition_cost,
            transaction_type=TransactionType.REFUND,
        )
        self.transactions.append(transaction)
        self._pending_transactions.append(transaction)

    def charge(self, amount: int) -> None:
        self.balance += amount
        transaction = CreditTransaction(
            amount=amount,
            transaction_type=TransactionType.CHARGE,
        )
        self.transactions.append(transaction)
        self._pending_transactions.append(transaction)
