from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from credit_account.adapter.outbound.models import CreditAccountModel, CreditTransactionModel
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import CreditAccount, CreditTransaction
from credit_account.domain.value_objects.transaction_type import TransactionType


class SqlAlchemyAsyncCreditAccountRepository(AsyncCreditAccountRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, account: CreditAccount) -> None:
        statement = (
            select(CreditAccountModel)
            .options(selectinload(CreditAccountModel.transactions))
            .where(CreditAccountModel.user_id == account.user_id)
        )
        existing = (await self._session.execute(statement)).scalar_one_or_none()
        if existing:
            existing.balance = account.balance
            existing_tx_ids = {transaction.id for transaction in existing.transactions}
            for transaction in account.transactions:
                if transaction.id not in existing_tx_ids:
                    existing.transactions.append(self._tx_to_model(transaction, account.user_id))
        else:
            self._session.add(CreditAccountModel(
                user_id=account.user_id,
                balance=account.balance,
                transactions=[self._tx_to_model(transaction, account.user_id) for transaction in account.transactions],
            ))
        await self._session.flush()

    async def find_credit_by_user_id(self, user_id: str, for_update: bool = False) -> CreditAccount | None:
        statement = (
            select(CreditAccountModel)
            .options(selectinload(CreditAccountModel.transactions))
            .where(CreditAccountModel.user_id == user_id)
        )
        if for_update:
            statement = statement.with_for_update()
        model = (await self._session.execute(statement)).scalar_one_or_none()
        if model is None:
            return None
        return CreditAccount(
            user_id=model.user_id,
            balance=model.balance,
            transactions=[
                CreditTransaction(
                    id=transaction.id,
                    amount=transaction.amount,
                    transaction_type=TransactionType(transaction.transaction_type),
                    created_at=transaction.created_at,
                )
                for transaction in model.transactions
            ],
        )

    def _tx_to_model(self, transaction: CreditTransaction, user_id: str) -> CreditTransactionModel:
        return CreditTransactionModel(
            id=transaction.id,
            account_user_id=user_id,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type.value,
            created_at=transaction.created_at,
        )
