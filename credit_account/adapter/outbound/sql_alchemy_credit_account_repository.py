from sqlalchemy.orm import Session

from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort
from credit_account.domain.aggregates.credit_account import CreditAccount, CreditTransaction
from credit_account.domain.value_objects.transaction_type import TransactionType


class SqlAlchemyCreditAccountRepository(CreditAccountRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, input: CreditAccount) -> None:
        existing = self._session.get(CreditAccountModel, input.user_id)
        if existing:
            existing.balance = input.balance
            existing_tx_ids = {t.id for t in existing.transactions}
            for tx in input.transactions:
                if tx.id not in existing_tx_ids:
                    existing.transactions.append(self._tx_to_model(tx, input.user_id))
        else:
            self._session.add(CreditAccountModel(
                user_id=input.user_id,
                balance=input.balance,
                transactions=[self._tx_to_model(tx, input.user_id) for tx in input.transactions],
            ))
        self._session.commit()

    def find_credit_by_user_id(self, user_id: str) -> CreditAccount:
        model = self._session.get(CreditAccountModel, user_id)
        if not model:
            raise ValueError(f"크레딧 계정을 찾을 수 없습니다: {user_id}")
        return CreditAccount(
            user_id=model.user_id,
            balance=model.balance,
            transactions=[
                CreditTransaction(
                    id=t.id,
                    amount=t.amount,
                    transaction_type=TransactionType(t.transaction_type),
                    created_at=t.created_at,
                )
                for t in model.transactions
            ],
        )

    def _tx_to_model(self, tx: CreditTransaction, user_id: str) -> CreditTransactionModel:
        return CreditTransactionModel(
            id=tx.id,
            account_user_id=user_id,
            amount=tx.amount,
            transaction_type=tx.transaction_type.value,
            created_at=tx.created_at,
        )
