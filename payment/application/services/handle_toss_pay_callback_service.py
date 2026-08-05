from payment.application.ports.inbound.handle_toss_pay_callback import (
    HandleTossPayCallbackCommand,
    HandleTossPayCallbackPort,
    HandleTossPayCallbackResult,
)
from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentCommand,
    ProcessVerifiedPaymentPort,
)
from payment.application.ports.outbound.payment_gateway.toss_pay_gateway import (
    GetTossPayStatusCommand,
    TossPayGatewayPort,
)
from payment.application.ports.outbound.persistence.async_payment_repository import (
    AsyncPaymentRepository,
)
from payment.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from payment.domain.value_objects.payment_provider import PaymentProvider
from shared.exceptions import (
    BusinessRuleException,
    ExternalServiceException,
    NotFoundException,
)


class HandleTossPayCallbackService(HandleTossPayCallbackPort):
    def __init__(
        self,
        toss_pay_gateway: TossPayGatewayPort,
        process_payment: ProcessVerifiedPaymentPort,
        payment_repo: AsyncPaymentRepository,
        transaction: AsyncTransaction,
    ):
        self._toss_pay_gateway = toss_pay_gateway
        self._process_payment = process_payment
        self._payment_repo = payment_repo
        self._transaction = transaction

    async def execute(
        self,
        command: HandleTossPayCallbackCommand,
    ) -> HandleTossPayCallbackResult:
        if command.status != "PAY_COMPLETE":
            raise BusinessRuleException("완료되지 않은 토스페이 콜백입니다")

        try:
            payment = await self._payment_repo.find_by_order_id(command.order_id)
            if payment is None or payment.provider != PaymentProvider.TOSS_PAY:
                raise NotFoundException("결제 주문을 찾을 수 없습니다")
            if payment.provider_payment_id != command.pay_token:
                raise BusinessRuleException("저장된 토스페이 결제 토큰이 일치하지 않습니다")
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        verified = await self._toss_pay_gateway.get_status(
            GetTossPayStatusCommand(order_id=command.order_id)
        )
        if verified.pay_status != "PAY_COMPLETE":
            raise BusinessRuleException("토스페이 결제가 완료되지 않았습니다")
        if verified.order_id != command.order_id:
            raise BusinessRuleException("토스페이 주문번호가 일치하지 않습니다")
        if verified.pay_token != command.pay_token:
            raise BusinessRuleException("토스페이 결제 토큰이 일치하지 않습니다")
        if verified.paid_at is None or verified.transaction_id is None:
            raise ExternalServiceException("토스페이 완료 정보를 확인할 수 없습니다")
        if verified.transaction_id != command.transaction_id:
            raise BusinessRuleException("토스페이 거래번호가 일치하지 않습니다")

        result = await self._process_payment.execute(
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
                payload=command.payload,
            )
        )
        return HandleTossPayCallbackResult(
            payment_id=result.payment_id,
            status=result.status,
            already_processed=result.already_processed,
        )
