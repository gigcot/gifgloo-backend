from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from credit_account.adapter.outbound.models import CreditTransactionModel
from credit_account.application.ports.outbound.persistence.async_credit_summary_reader import (
    AsyncCreditSummaryReader,
)
from credit_account.domain.aggregates.credit_account import CreditTransaction
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType


class SqlAlchemyAsyncCreditSummaryReader(AsyncCreditSummaryReader):
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory

    async def find_transactions_by_source(
        self,
        user_id: str,
        source_type: CreditSourceType,
        source_id: str,
    ) -> list[CreditTransaction]:
        statement = (
            select(CreditTransactionModel)
            .where(
                CreditTransactionModel.account_user_id == user_id,
                CreditTransactionModel.source_type == source_type.value,
                CreditTransactionModel.source_id == source_id,
            )
            .order_by(
                CreditTransactionModel.created_at,
                CreditTransactionModel.id,
            )
        )
        async with self._session_factory() as session:
            models = (await session.scalars(statement)).all()

        return [
            CreditTransaction(
                id=model.id,
                amount=model.amount,
                transaction_type=TransactionType(model.transaction_type),
                source_type=CreditSourceType(model.source_type),
                source_id=model.source_id,
                credit_lot_id=model.credit_lot_id,
                reason=model.reason,
                balance_after=model.balance_after,
                created_at=model.created_at,
            )
            for model in models
        ]
