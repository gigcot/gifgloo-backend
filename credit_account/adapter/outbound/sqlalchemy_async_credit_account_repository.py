from datetime import datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from credit_account.adapter.outbound.models import (
    CreditAccountModel,
    CreditLotModel,
    CreditTransactionModel,
)
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import (
    CreditAccount,
    CreditLot,
    CreditTransaction,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.available_credit_summary import (
    AvailableCreditSummary,
)
from credit_account.domain.value_objects.transaction_type import TransactionType


def _lot_to_domain(model: CreditLotModel) -> CreditLot:
    return CreditLot(
        id=model.id,
        granted_amount=model.granted_amount,
        remaining_amount=model.remaining_amount,
        expires_at=model.expires_at,
        source_type=CreditSourceType(model.source_type) if model.source_type else None,
        source_id=model.source_id,
        created_at=model.created_at,
    )


def _transaction_to_domain(model: CreditTransactionModel) -> CreditTransaction:
    return CreditTransaction(
        id=model.id,
        amount=model.amount,
        transaction_type=TransactionType(model.transaction_type),
        source_type=CreditSourceType(model.source_type) if model.source_type else None,
        source_id=model.source_id,
        credit_lot_id=model.credit_lot_id,
        reason=model.reason,
        balance_after=model.balance_after,
        created_at=model.created_at,
    )


class SqlAlchemyAsyncCreditAccountRepository(AsyncCreditAccountRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, account: CreditAccount) -> None:
        await self._session.execute(
            update(CreditAccountModel)
            .where(CreditAccountModel.user_id == account.user_id)
            .values(balance=account.balance)
        )
        pending_lot_ids = {lot.id for lot in account.pending_lots}
        for lot in account.pending_lots:
            self._session.add(self._lot_to_model(lot, account.user_id))
        for lot in account.lots:
            if lot.id not in account.changed_lot_ids or lot.id in pending_lot_ids:
                continue
            await self._session.execute(
                update(CreditLotModel)
                .where(CreditLotModel.id == lot.id)
                .values(remaining_amount=lot.remaining_amount)
            )
        for transaction in account.pending_transactions:
            self._session.add(self._transaction_to_model(transaction, account.user_id))
        await self._session.flush()
        account.mark_pending_changes_persisted()

    async def find_for_update(
        self,
        user_id: str,
        required_lot_id: str | None = None,
    ) -> CreditAccount | None:
        account_statement = (
            select(CreditAccountModel)
            .where(CreditAccountModel.user_id == user_id)
            .with_for_update()
        )
        account_model = (
            await self._session.execute(account_statement)
        ).scalar_one_or_none()
        if account_model is None:
            return None
        required_lot_condition = (
            CreditLotModel.id == required_lot_id
            if required_lot_id is not None
            else False
        )
        lots_statement = (
            select(CreditLotModel)
            .where(
                CreditLotModel.account_user_id == user_id,
                or_(
                    CreditLotModel.remaining_amount > 0,
                    required_lot_condition,
                ),
            )
            .order_by(CreditLotModel.expires_at, CreditLotModel.created_at)
            .with_for_update()
        )
        lot_models = (await self._session.scalars(lots_statement)).all()
        return CreditAccount(
            user_id=account_model.user_id,
            balance=account_model.balance,
            transactions=[],
            lots=[_lot_to_domain(model) for model in lot_models],
        )

    async def find_available_summary_by_user_id(
        self,
        user_id: str,
        now: datetime,
    ) -> AvailableCreditSummary | None:
        statement = (
            select(
                func.coalesce(func.sum(CreditLotModel.remaining_amount), 0),
                func.min(CreditLotModel.expires_at),
            )
            .select_from(CreditAccountModel)
            .outerjoin(
                CreditLotModel,
                and_(
                    CreditLotModel.account_user_id == CreditAccountModel.user_id,
                    CreditLotModel.remaining_amount > 0,
                    CreditLotModel.expires_at > now,
                ),
            )
            .where(CreditAccountModel.user_id == user_id)
            .group_by(CreditAccountModel.user_id)
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        return AvailableCreditSummary(
            balance=row[0],
            nearest_expires_at=row[1],
        )

    async def exists_transaction_by_source(
        self,
        source_type: CreditSourceType,
        source_id: str,
    ) -> bool:
        statement = select(CreditTransactionModel.id).where(
            CreditTransactionModel.source_type == source_type.value,
            CreditTransactionModel.source_id == source_id,
        ).limit(1)
        return (await self._session.execute(statement)).scalar_one_or_none() is not None

    async def find_transaction_by_source(
        self,
        user_id: str,
        transaction_type: TransactionType,
        source_type: CreditSourceType,
        source_id: str,
    ) -> CreditTransaction | None:
        statement = select(CreditTransactionModel).where(
            CreditTransactionModel.account_user_id == user_id,
            CreditTransactionModel.transaction_type == transaction_type.value,
            CreditTransactionModel.source_type == source_type.value,
            CreditTransactionModel.source_id == source_id,
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _transaction_to_domain(model) if model else None

    async def find_lot_page_by_user_id(
        self,
        user_id: str,
        source_type: CreditSourceType,
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
    ) -> list[CreditLot]:
        statement = select(CreditLotModel).where(
            CreditLotModel.account_user_id == user_id,
            CreditLotModel.source_type == source_type.value,
        )
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    CreditLotModel.created_at < cursor_created_at,
                    and_(
                        CreditLotModel.created_at == cursor_created_at,
                        CreditLotModel.id < cursor_id,
                    ),
                )
            )
        statement = statement.order_by(
            CreditLotModel.created_at.desc(),
            CreditLotModel.id.desc(),
        ).limit(limit)
        models = (await self._session.scalars(statement)).all()
        return [_lot_to_domain(model) for model in models]

    async def find_transaction_page_by_user_id(
        self,
        user_id: str,
        transaction_types: frozenset[TransactionType],
        limit: int,
        cursor_created_at: datetime | None,
        cursor_id: str | None,
    ) -> list[CreditTransaction]:
        statement = select(CreditTransactionModel).where(
            CreditTransactionModel.account_user_id == user_id,
            CreditTransactionModel.transaction_type.in_(
                tuple(
                    transaction_type.value
                    for transaction_type in transaction_types
                )
            ),
        )
        if cursor_created_at is not None and cursor_id is not None:
            statement = statement.where(
                or_(
                    CreditTransactionModel.created_at < cursor_created_at,
                    and_(
                        CreditTransactionModel.created_at == cursor_created_at,
                        CreditTransactionModel.id < cursor_id,
                    ),
                )
            )
        statement = statement.order_by(
            CreditTransactionModel.created_at.desc(),
            CreditTransactionModel.id.desc(),
        ).limit(limit)
        models = (await self._session.scalars(statement)).all()
        return [_transaction_to_domain(model) for model in models]

    @staticmethod
    def _lot_to_model(lot: CreditLot, user_id: str) -> CreditLotModel:
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

    @staticmethod
    def _transaction_to_model(
        transaction: CreditTransaction,
        user_id: str,
    ) -> CreditTransactionModel:
        return CreditTransactionModel(
            id=transaction.id,
            account_user_id=user_id,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type.value,
            source_type=transaction.source_type.value if transaction.source_type else None,
            source_id=transaction.source_id,
            credit_lot_id=transaction.credit_lot_id,
            reason=transaction.reason,
            balance_after=transaction.balance_after,
            created_at=transaction.created_at,
        )
