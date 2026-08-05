from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from payment.adapter.outbound.persistence.models import PaymentModel
from payment.application.ports.outbound.persistence.async_payment_repository import (
    AsyncPaymentRepository,
)
from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_status import PaymentStatus
from payment.domain.value_objects.pg_type import PgType


def _to_domain(model: PaymentModel) -> Payment:
    payment = object.__new__(Payment)
    payment.id = model.id
    payment.user_id = model.user_id
    payment.provider = PaymentProvider(model.provider)
    payment.pg_type = PgType(model.provider)
    payment.order_id = model.order_id
    payment.amount = model.amount
    payment.currency = model.currency
    payment.credit_amount = model.credit_amount
    payment.provider_payment_id = model.provider_payment_id
    payment.provider_transaction_id = model.provider_transaction_id
    payment.status = PaymentStatus(model.status)
    payment.failed_reason = model.failed_reason
    payment.cancel_reason = model.cancel_reason
    payment.created_at = model.created_at
    payment.updated_at = model.updated_at
    payment.authorized_at = model.authorized_at
    payment.approved_at = model.approved_at
    payment.canceled_at = model.canceled_at
    payment.credit_granted_at = model.credit_granted_at
    return payment


class SqlAlchemyAsyncPaymentRepository(AsyncPaymentRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, payment: Payment) -> None:
        self._session.add(PaymentModel(
            id=payment.id,
            user_id=payment.user_id,
            provider=payment.provider.value,
            order_id=payment.order_id,
            amount=payment.amount,
            currency=payment.currency,
            credit_amount=payment.credit_amount,
            provider_payment_id=payment.provider_payment_id,
            provider_transaction_id=payment.provider_transaction_id,
            status=payment.status.value,
            failed_reason=payment.failed_reason,
            cancel_reason=payment.cancel_reason,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
            authorized_at=payment.authorized_at,
            approved_at=payment.approved_at,
            canceled_at=payment.canceled_at,
            credit_granted_at=payment.credit_granted_at,
        ))
        await self._session.flush()

    async def update(self, payment: Payment) -> None:
        await self._session.execute(
            update(PaymentModel)
            .where(PaymentModel.id == payment.id)
            .values(
                provider_payment_id=payment.provider_payment_id,
                provider_transaction_id=payment.provider_transaction_id,
                status=payment.status.value,
                failed_reason=payment.failed_reason,
                cancel_reason=payment.cancel_reason,
                updated_at=payment.updated_at,
                authorized_at=payment.authorized_at,
                approved_at=payment.approved_at,
                canceled_at=payment.canceled_at,
                credit_granted_at=payment.credit_granted_at,
            )
        )
        await self._session.flush()

    async def find_by_order_id(self, order_id: str) -> Payment | None:
        statement = select(PaymentModel).where(PaymentModel.order_id == order_id)
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_by_order_id_for_update(self, order_id: str) -> Payment | None:
        statement = (
            select(PaymentModel)
            .where(PaymentModel.order_id == order_id)
            .with_for_update()
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_by_id(self, payment_id: str) -> Payment | None:
        statement = select(PaymentModel).where(PaymentModel.id == payment_id)
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def find_all_by_user_id(self, user_id: str) -> list[Payment]:
        statement = (
            select(PaymentModel)
            .where(PaymentModel.user_id == user_id)
            .order_by(PaymentModel.created_at.desc())
        )
        models = (await self._session.scalars(statement)).all()
        return [_to_domain(model) for model in models]
