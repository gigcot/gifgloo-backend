from sqlalchemy.orm import Session

from credit_account.adapter.outbound.models import CreditAccountModel, CreditLotModel, CreditTransactionModel
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort
from credit_account.domain.aggregates.credit_account import CreditAccount, CreditLot, CreditTransaction
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType


class SqlAlchemyCreditAccountRepository(CreditAccountRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, input: CreditAccount) -> None:
        existing = self._session.get(CreditAccountModel, input.user_id)
        if existing:
            existing.balance = input.balance
            for lot in input.pending_lots:
                self._session.add(self._lot_to_model(lot, input.user_id))
            for lot in input.lots:
                if lot.id in input.changed_lot_ids:
                    model = self._session.get(CreditLotModel, lot.id)
                    model.remaining_amount = lot.remaining_amount
            for transaction in input.pending_transactions:
                self._session.add(self._tx_to_model(transaction, input.user_id))
        else:
            self._session.add(CreditAccountModel(
                user_id=input.user_id,
                balance=input.balance,
                lots=[self._lot_to_model(lot, input.user_id) for lot in input.lots],
                transactions=[self._tx_to_model(tx, input.user_id) for tx in input.transactions],
            ))
        self._session.commit()
        input.mark_pending_changes_persisted()

    def find_credit_by_user_id(self, user_id: str) -> CreditAccount | None:
        model = self._session.get(CreditAccountModel, user_id)
        if not model:
            return None
        return CreditAccount(
            user_id=model.user_id,
            balance=model.balance,
            lots=[
                CreditLot(
                    id=lot.id,
                    granted_amount=lot.granted_amount,
                    remaining_amount=lot.remaining_amount,
                    expires_at=lot.expires_at,
                    source_type=CreditSourceType(lot.source_type) if lot.source_type else None,
                    source_id=lot.source_id,
                    created_at=lot.created_at,
                )
                for lot in model.lots
            ],
            transactions=[
                CreditTransaction(
                    id=t.id,
                    amount=t.amount,
                    transaction_type=TransactionType(t.transaction_type),
                    source_type=CreditSourceType(t.source_type) if t.source_type else None,
                    source_id=t.source_id,
                    credit_lot_id=t.credit_lot_id,
                    reason=t.reason,
                    balance_after=t.balance_after,
                    created_at=t.created_at,
                )
                for t in model.transactions
            ],
        )

    def _lot_to_model(self, lot: CreditLot, user_id: str) -> CreditLotModel:
        return CreditLotModel(
            id=lot.id,
            account_user_id=user_id,
            source_type=lot.source_type.value if lot.source_type else None,
            source_id=lot.source_id,
            granted_amount=lot.granted_amount,
            remaining_amount=lot.remaining_amount,
            expires_at=lot.expires_at,
            created_at=lot.created_at,
        )

    def _tx_to_model(self, tx: CreditTransaction, user_id: str) -> CreditTransactionModel:
        return CreditTransactionModel(
            id=tx.id,
            account_user_id=user_id,
            amount=tx.amount,
            transaction_type=tx.transaction_type.value,
            source_type=tx.source_type.value if tx.source_type else None,
            source_id=tx.source_id,
            credit_lot_id=tx.credit_lot_id,
            reason=tx.reason,
            balance_after=tx.balance_after,
            created_at=tx.created_at,
        )
