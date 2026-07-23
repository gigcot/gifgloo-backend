from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import CreditAccount, CreditTransaction


class SqlAlchemyAsyncCreditAccountRepository(AsyncCreditAccountRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, account: CreditAccount) -> None:
        await self._session.execute(
            update(CreditAccountModel)
            .where(CreditAccountModel.user_id == account.user_id)
            .values(balance=account.balance)
        )
        for transaction in account.pending_transactions:
            self._session.add(self._tx_to_model(transaction, account.user_id))
        await self._session.flush()
        account.mark_pending_transactions_persisted()

    async def find_for_update(self, user_id: str) -> CreditAccount | None:
        statement = (
            select(CreditAccountModel)
            .where(CreditAccountModel.user_id == user_id)
            .with_for_update()
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        if model is None:
            return None
        return CreditAccount(
            user_id=model.user_id,
            balance=model.balance,
            transactions=[],
        )

    async def find_balance_by_user_id(self, user_id: str) -> CreditAccount | None:
        statement = select(
            CreditAccountModel.user_id,
            CreditAccountModel.balance,
        ).where(CreditAccountModel.user_id == user_id)
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return CreditAccount(user_id=row.user_id, balance=row.balance, transactions=[])

    def _tx_to_model(self, transaction: CreditTransaction, user_id: str) -> CreditTransactionModel:
        return CreditTransactionModel(
            id=transaction.id,
            account_user_id=user_id,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type.value,
            created_at=transaction.created_at,
        )
