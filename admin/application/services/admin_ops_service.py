from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from admin.adapter.outbound.persistence.sqlalchemy_admin_ops_query import (
    SqlAlchemyAdminOpsQuery,
    _iso,
)
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import (
    SqlAlchemyAsyncCreditAccountRepository,
)
from credit_account.application.ports.inbound.grant_payment_credit import (
    GrantPaymentCreditCommand,
)
from credit_account.application.services.grant_payment_credit_service import (
    GrantPaymentCreditService,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from payment.adapter.outbound.domain_bridges.async_credit_grant_adapter import (
    AsyncCreditGrantAdapter,
)
from payment.adapter.outbound.persistence.sqlalchemy_async_payment_repository import (
    SqlAlchemyAsyncPaymentRepository,
)
from payment.adapter.outbound.persistence.sqlalchemy_async_transaction import (
    SqlAlchemyAsyncTransaction,
)
from payment.adapter.outbound.persistence.sqlalchemy_payment_inbox import (
    SqlAlchemyPaymentInbox,
)
from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentCommand,
)
from payment.application.ports.outbound.payment_gateway.toss_pay_gateway import (
    GetTossPayStatusCommand,
    TossPayGatewayPort,
)
from payment.application.services.process_verified_payment_service import (
    ProcessVerifiedPaymentService,
)
from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_status import PaymentStatus
from shared.exceptions import BusinessRuleException, NotFoundException


class AdminOpsService:
    def __init__(
        self,
        session: AsyncSession,
        toss_pay_gateway: TossPayGatewayPort,
    ):
        self._session = session
        self._toss_pay_gateway = toss_pay_gateway
        self._query = SqlAlchemyAdminOpsQuery(session)

    async def recheck_payment(self, admin_user_id: str, payment_id: str) -> dict:
        payment_repo = SqlAlchemyAsyncPaymentRepository(self._session)
        payment = await payment_repo.find_by_id(payment_id)
        if payment is None:
            raise NotFoundException("결제를 찾을 수 없습니다")
        if payment.provider != PaymentProvider.TOSS_PAY:
            raise BusinessRuleException("토스페이 결제만 재조회할 수 있습니다")

        verified = await self._toss_pay_gateway.get_status(
            GetTossPayStatusCommand(order_id=payment.order_id)
        )
        processed = None
        if verified.pay_status == "PAY_COMPLETE":
            if verified.paid_at is None or verified.transaction_id is None:
                raise BusinessRuleException("토스페이 완료 정보가 부족합니다")
            result = await self._process_verified_payment_service().execute(
                ProcessVerifiedPaymentCommand(
                    provider=PaymentProvider.TOSS_PAY,
                    external_event_id=verified.transaction_id,
                    event_type="PAY_COMPLETE",
                    order_id=verified.order_id,
                    provider_payment_id=verified.pay_token,
                    provider_transaction_id=verified.transaction_id,
                    amount=verified.amount,
                    currency="KRW",
                    approved_at=verified.paid_at,
                    payload={"source": "ADMIN_RECHECK", "pay_status": verified.pay_status},
                )
            )
            processed = {
                "payment_id": result.payment_id,
                "status": result.status.value,
                "already_processed": result.already_processed,
            }

        self._session.add(self._query.make_audit_log(
            admin_user_id=admin_user_id,
            action="PAYMENT_RECHECK",
            target_type="PAYMENT",
            target_id=payment_id,
            reason="토스 결제 상태 재조회",
            metadata={
                "order_id": payment.order_id,
                "pay_status": verified.pay_status,
                "processed": processed,
            },
        ))
        await self._session.commit()

        payment_snapshot = await self._query.payment_snapshot(payment_id)
        if payment_snapshot is None:
            raise NotFoundException("결제를 찾을 수 없습니다")

        return {
            "toss": {
                "order_id": verified.order_id,
                "pay_token": verified.pay_token,
                "pay_status": verified.pay_status,
                "amount": verified.amount,
                "paid_at": _iso(verified.paid_at),
                "transaction_id": verified.transaction_id,
            },
            "processed": processed,
            "payment": payment_snapshot,
        }

    async def grant_credit(
        self,
        admin_user_id: str,
        user_id: str,
        amount: int,
        reason: str,
        idempotency_key: str,
        payment_id: str | None = None,
    ) -> dict:
        existing_audit = await self._query.find_audit_by_idempotency_key(idempotency_key)
        if existing_audit is not None:
            return await self._idempotent_grant_response(
                existing_audit,
                user_id,
                amount,
                payment_id,
            )

        if not await self._query.user_exists(user_id):
            raise NotFoundException("사용자를 찾을 수 없습니다")

        if payment_id:
            audit = await self._grant_payment_credit(
                admin_user_id,
                user_id,
                amount,
                reason,
                idempotency_key,
                payment_id,
            )
        else:
            audit = await self._grant_admin_credit(
                admin_user_id,
                user_id,
                amount,
                reason,
                idempotency_key,
            )

        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            existing_audit = await self._query.find_audit_by_idempotency_key(idempotency_key)
            if existing_audit is None:
                raise
            return await self._idempotent_grant_response(
                existing_audit,
                user_id,
                amount,
                payment_id,
            )
        return {
            "ok": True,
            "audit_id": audit.id,
            "user_id": user_id,
            "balance": await self._query.current_balance(user_id),
            "idempotent": False,
        }

    async def _idempotent_grant_response(
        self,
        existing_audit,
        user_id: str,
        amount: int,
        payment_id: str | None,
    ) -> dict:
        metadata = existing_audit.metadata_json
        if (
            metadata["user_id"] != user_id
            or metadata["amount"] != amount
            or metadata["payment_id"] != payment_id
        ):
            raise BusinessRuleException("이미 다른 크레딧 지급 요청에 사용된 멱등키입니다")
        return {
            "ok": True,
            "audit_id": existing_audit.id,
            "user_id": user_id,
            "balance": await self._query.current_balance(user_id),
            "idempotent": True,
        }

    async def _grant_payment_credit(
        self,
        admin_user_id: str,
        user_id: str,
        amount: int,
        reason: str,
        idempotency_key: str,
        payment_id: str,
    ):
        payment_repo = SqlAlchemyAsyncPaymentRepository(self._session)
        payment = await payment_repo.find_by_id(payment_id)
        if payment is None:
            raise NotFoundException("결제를 찾을 수 없습니다")
        if payment.user_id != user_id:
            raise BusinessRuleException("결제 사용자와 지급 대상이 다릅니다")
        if payment.status != PaymentStatus.APPROVED:
            raise BusinessRuleException("완료된 결제만 결제 기반 수동 지급할 수 있습니다")
        if payment.credit_granted_at is not None:
            raise BusinessRuleException("이미 지급 완료 처리된 결제입니다")
        if payment.credit_amount != amount:
            raise BusinessRuleException("결제 기반 수동 지급은 결제 크레딧 수량과 같아야 합니다")

        granted = await GrantPaymentCreditService(
            SqlAlchemyAsyncCreditAccountRepository(self._session)
        ).execute(
            GrantPaymentCreditCommand(
                user_id=user_id,
                amount=amount,
                payment_id=payment.id,
            )
        )
        if not granted.granted:
            raise BusinessRuleException("이미 이 결제의 크레딧 지급 내역이 있습니다")
        payment.mark_credit_granted()
        await payment_repo.update(payment)
        audit = self._query.make_audit_log(
            admin_user_id=admin_user_id,
            action="PAYMENT_CREDIT_GRANT",
            target_type="PAYMENT",
            target_id=payment.id,
            reason=reason,
            metadata={"user_id": user_id, "amount": amount, "payment_id": payment.id},
            idempotency_key=idempotency_key,
        )
        self._session.add(audit)
        return audit

    async def _grant_admin_credit(
        self,
        admin_user_id: str,
        user_id: str,
        amount: int,
        reason: str,
        idempotency_key: str,
    ):
        audit = self._query.make_audit_log(
            admin_user_id=admin_user_id,
            action="ADMIN_CREDIT_GRANT",
            target_type="USER",
            target_id=user_id,
            reason=reason,
            metadata={"user_id": user_id, "amount": amount, "payment_id": None},
            idempotency_key=idempotency_key,
        )
        credit_repo = SqlAlchemyAsyncCreditAccountRepository(self._session)
        credit_account = await credit_repo.find_for_update(user_id)
        if credit_account is None:
            raise NotFoundException("크레딧 계정을 찾을 수 없습니다")
        credit_account.charge(
            amount,
            source_type=CreditSourceType.ADMIN,
            source_id=audit.id,
            reason=reason,
        )
        await credit_repo.save(credit_account)
        self._session.add(audit)
        return audit

    def _process_verified_payment_service(self) -> ProcessVerifiedPaymentService:
        return ProcessVerifiedPaymentService(
            payment_repo=SqlAlchemyAsyncPaymentRepository(self._session),
            inbox=SqlAlchemyPaymentInbox(self._session),
            credit=AsyncCreditGrantAdapter(
                GrantPaymentCreditService(
                    SqlAlchemyAsyncCreditAccountRepository(self._session)
                )
            ),
            transaction=SqlAlchemyAsyncTransaction(self._session),
        )
