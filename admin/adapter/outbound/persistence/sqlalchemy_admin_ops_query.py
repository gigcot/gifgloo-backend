from datetime import datetime, timezone
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.adapter.outbound.persistence.models import AdminAuditLogModel
from composition.adapter.outbound.persistence.models import CompositionJobModel
from credit_account.adapter.outbound.models import (
    CreditAccountModel,
    CreditTransactionModel,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from payment.adapter.outbound.persistence.models import PaymentModel
from payment.domain.value_objects.payment_status import PaymentStatus
from user.adapter.outbound.persistence.models import UserModel


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class SqlAlchemyAdminOpsQuery:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_overview(self, admin_user_id: str) -> dict:
        kst_start = datetime.now(ZoneInfo("Asia/Seoul")).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        day_start = kst_start.astimezone(timezone.utc)

        payment_credit_exists = exists(
            select(CreditTransactionModel.id).where(
                CreditTransactionModel.source_type == CreditSourceType.PAYMENT.value,
                CreditTransactionModel.source_id == PaymentModel.id,
            )
        )

        today_compositions = await self._session.scalar(
            select(func.count()).select_from(CompositionJobModel).where(
                CompositionJobModel.created_at >= day_start,
            )
        )
        today_failed = await self._session.scalar(
            select(func.count()).select_from(CompositionJobModel).where(
                CompositionJobModel.created_at >= day_start,
                CompositionJobModel.status == "FAILED",
            )
        )
        today_payment_amount = await self._session.scalar(
            select(func.coalesce(func.sum(PaymentModel.amount), 0)).where(
                PaymentModel.approved_at >= day_start,
                PaymentModel.status == PaymentStatus.APPROVED.value,
            )
        )
        today_credit_grants = await self._session.scalar(
            select(func.coalesce(func.sum(CreditTransactionModel.amount), 0)).where(
                CreditTransactionModel.created_at >= day_start,
                CreditTransactionModel.transaction_type == "CHARGE",
            )
        )
        missing_credit_candidates = await self._session.scalar(
            select(func.count()).select_from(PaymentModel).where(
                PaymentModel.status == PaymentStatus.APPROVED.value,
                PaymentModel.credit_granted_at.is_(None),
                ~payment_credit_exists,
            )
        )

        return {
            "admin_user_id": admin_user_id,
            "today_compositions": today_compositions or 0,
            "today_failed_compositions": today_failed or 0,
            "today_payment_amount": today_payment_amount or 0,
            "today_credit_grants": today_credit_grants or 0,
            "missing_credit_candidates": missing_credit_candidates or 0,
        }

    async def get_credit_case(self, admin_user_id: str, query: str) -> dict | None:
        user = await self._find_user_for_credit_case(query)
        if user is None:
            return None

        credit_account = await self._session.get(CreditAccountModel, user.id)
        payments = (
            await self._session.execute(
                select(PaymentModel)
                .where(PaymentModel.user_id == user.id)
                .order_by(PaymentModel.created_at.desc())
                .limit(30)
            )
        ).scalars().all()
        payment_credit_sources = await self._payment_credit_source_set(
            [payment.id for payment in payments],
        )
        credit_transactions = (
            await self._session.execute(
                select(CreditTransactionModel)
                .where(CreditTransactionModel.account_user_id == user.id)
                .order_by(CreditTransactionModel.created_at.desc())
                .limit(50)
            )
        ).scalars().all()

        return {
            "admin_user_id": admin_user_id,
            "user": {
                "id": user.id,
                "email": user.email,
                "provider": user.provider,
                "role": user.role,
                "status": user.status,
                "created_at": _iso(user.created_at),
                "credit_balance": credit_account.balance if credit_account else 0,
            },
            "payments": [
                self._payment_dict(payment, payment.id in payment_credit_sources)
                for payment in payments
            ],
            "credit_transactions": [
                self._credit_transaction_dict(transaction)
                for transaction in credit_transactions
            ],
        }

    async def payment_snapshot(self, payment_id: str) -> dict | None:
        payment = await self._session.get(PaymentModel, payment_id)
        if payment is None:
            return None
        credit_sources = await self._payment_credit_source_set([payment_id])
        return self._payment_dict(payment, payment_id in credit_sources)

    async def user_exists(self, user_id: str) -> bool:
        return await self._session.get(UserModel, user_id) is not None

    async def current_balance(self, user_id: str) -> int:
        credit_account = await self._session.get(CreditAccountModel, user_id)
        return credit_account.balance if credit_account else 0

    async def find_audit_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> AdminAuditLogModel | None:
        statement = select(AdminAuditLogModel).where(
            AdminAuditLogModel.idempotency_key == idempotency_key,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    def make_audit_log(
        self,
        admin_user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        reason: str,
        metadata: dict,
        idempotency_key: str | None = None,
    ) -> AdminAuditLogModel:
        return AdminAuditLogModel(
            id=str(uuid.uuid4()),
            admin_user_id=admin_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            metadata_json=metadata,
            idempotency_key=idempotency_key,
            created_at=datetime.now(timezone.utc),
        )

    async def _find_user_for_credit_case(self, query: str) -> UserModel | None:
        normalized = query.strip()
        payment_statement = select(PaymentModel).where(
            or_(
                PaymentModel.id == normalized,
                PaymentModel.order_id == normalized,
                PaymentModel.provider_payment_id == normalized,
                PaymentModel.provider_transaction_id == normalized,
            )
        )
        payment = (await self._session.execute(payment_statement)).scalars().first()
        if payment:
            return await self._session.get(UserModel, payment.user_id)

        user_statement = select(UserModel).where(
            or_(
                UserModel.id == normalized,
                func.lower(UserModel.email) == normalized.lower(),
            )
        )
        return (await self._session.execute(user_statement)).scalars().first()

    async def _payment_credit_source_set(self, payment_ids: list[str]) -> set[str]:
        if not payment_ids:
            return set()
        statement = select(CreditTransactionModel.source_id).where(
            CreditTransactionModel.source_type == CreditSourceType.PAYMENT.value,
            CreditTransactionModel.source_id.in_(payment_ids),
        )
        return {
            source_id
            for source_id in (await self._session.execute(statement)).scalars().all()
            if source_id is not None
        }

    def _payment_dict(self, payment: PaymentModel, credit_transaction_exists: bool) -> dict:
        needs_credit_grant = (
            payment.status == PaymentStatus.APPROVED.value
            and payment.credit_granted_at is None
            and not credit_transaction_exists
        )
        return {
            "id": payment.id,
            "user_id": payment.user_id,
            "provider": payment.provider,
            "order_id": payment.order_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "credit_amount": payment.credit_amount,
            "provider_payment_id": payment.provider_payment_id,
            "provider_transaction_id": payment.provider_transaction_id,
            "status": payment.status,
            "failed_reason": payment.failed_reason,
            "cancel_reason": payment.cancel_reason,
            "created_at": _iso(payment.created_at),
            "updated_at": _iso(payment.updated_at),
            "approved_at": _iso(payment.approved_at),
            "canceled_at": _iso(payment.canceled_at),
            "credit_granted_at": _iso(payment.credit_granted_at),
            "credit_transaction_exists": credit_transaction_exists,
            "needs_credit_grant": needs_credit_grant,
        }

    def _credit_transaction_dict(self, transaction: CreditTransactionModel) -> dict:
        return {
            "id": transaction.id,
            "user_id": transaction.account_user_id,
            "amount": transaction.amount,
            "transaction_type": transaction.transaction_type,
            "source_type": transaction.source_type,
            "source_id": transaction.source_id,
            "reason": transaction.reason,
            "created_at": _iso(transaction.created_at),
        }
