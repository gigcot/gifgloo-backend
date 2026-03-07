from dataclasses import dataclass, field
from datetime import datetime, timezone
from credit_account.domain.value_objects.credit_policy import CreditPolicy
from credit_account.domain.value_objects.transaction_type import TransactionType
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

    def _is_sufficient(self):
        return self.balance >= self.composition_cost

    def deduct(self):
        if not self._is_sufficient(self):
            raise ValueError("잔액이 충분하지 않습니다")
        self.balance -= self.composition_cost
        transaction = CreditTransaction(
            amount=self.composition_cost,
            transaction_type=TransactionType.DEDUCT,
        )
        self.transactions.append(transaction)

    def charge(self, amount):
        self.balance += amount
        transaction = CreditTransaction(
            amount=amount,
            transaction_type=TransactionType.CHARGE,
        )
        self.transactions.append(transaction)