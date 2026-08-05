from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentCommand,
    ProcessVerifiedPaymentPort,
    ProcessVerifiedPaymentResult,
)
from payment.application.ports.outbound.domain_bridges.credit_grant_port import (
    CreditGrantPort,
    GrantPaymentCreditCommand,
)
from payment.application.ports.outbound.inbox.payment_inbox_port import (
    AcquirePaymentInboxCommand,
    PaymentInboxPort,
)
from payment.application.ports.outbound.persistence.async_payment_repository import (
    AsyncPaymentRepository,
)
from payment.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from shared.exceptions import InvalidStateException, NotFoundException


class ProcessVerifiedPaymentService(ProcessVerifiedPaymentPort):
    def __init__(
        self,
        payment_repo: AsyncPaymentRepository,
        inbox: PaymentInboxPort,
        credit: CreditGrantPort,
        transaction: AsyncTransaction,
    ):
        self._payment_repo = payment_repo
        self._inbox = inbox
        self._credit = credit
        self._transaction = transaction

    async def execute(
        self,
        command: ProcessVerifiedPaymentCommand,
    ) -> ProcessVerifiedPaymentResult:
        try:
            inbox_result = await self._inbox.acquire(
                AcquirePaymentInboxCommand(
                    provider=command.provider,
                    external_event_id=command.external_event_id,
                    event_type=command.event_type,
                    order_id=command.order_id,
                    payload=command.payload,
                )
            )
            if inbox_result.already_processed:
                if inbox_result.payment_id is None:
                    raise InvalidStateException("처리된 결제 알림에 결제 식별자가 없습니다")
                payment = await self._payment_repo.find_by_id(inbox_result.payment_id)
                if payment is None:
                    raise NotFoundException("처리된 결제를 찾을 수 없습니다")
                await self._transaction.commit()
                return ProcessVerifiedPaymentResult(
                    payment_id=inbox_result.payment_id,
                    status=payment.status,
                    already_processed=True,
                )

            payment = await self._payment_repo.find_by_order_id_for_update(command.order_id)
            if payment is None:
                raise NotFoundException("결제 주문을 찾을 수 없습니다")

            payment.validate_approval(
                provider=command.provider,
                amount=command.amount,
                currency=command.currency,
            )
            payment.approve(
                provider_payment_id=command.provider_payment_id,
                provider_transaction_id=command.provider_transaction_id,
                approved_at=command.approved_at,
            )

            if payment.can_grant_credit():
                await self._credit.grant(
                    GrantPaymentCreditCommand(
                        user_id=payment.user_id,
                        amount=payment.credit_amount,
                        payment_id=payment.id,
                    )
                )
                payment.mark_credit_granted()

            await self._payment_repo.update(payment)
            await self._inbox.mark_processed(
                command.provider,
                command.external_event_id,
                payment.id,
            )
            await self._transaction.commit()
            return ProcessVerifiedPaymentResult(
                payment_id=payment.id,
                status=payment.status,
                already_processed=False,
            )
        except Exception:
            await self._transaction.rollback()
            raise
