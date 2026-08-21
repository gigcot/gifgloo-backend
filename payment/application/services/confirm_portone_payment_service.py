from payment.application.ports.inbound.confirm_portone_payment import (
    ConfirmPortOnePaymentCommand,
    ConfirmPortOnePaymentPort,
    ConfirmPortOnePaymentResult,
)
from payment.application.ports.inbound.process_verified_payment import (
    ProcessVerifiedPaymentCommand,
    ProcessVerifiedPaymentPort,
)
from payment.application.ports.outbound.payment_gateway.portone_gateway import (
    GetPortOnePaymentCommand,
    PortOneGatewayPort,
)
from payment.application.ports.outbound.persistence.async_payment_repository import (
    AsyncPaymentRepository,
)
from payment.domain.value_objects.payment_environment import PaymentEnvironment
from payment.domain.value_objects.payment_provider import PaymentProvider
from shared.exceptions import AuthorizationException, BusinessRuleException, NotFoundException


class ConfirmPortOnePaymentService(ConfirmPortOnePaymentPort):
    def __init__(
        self,
        portone_gateway: PortOneGatewayPort,
        process_payment: ProcessVerifiedPaymentPort,
        payment_repo: AsyncPaymentRepository,
        expected_environment: PaymentEnvironment,
    ):
        self._portone_gateway = portone_gateway
        self._process_payment = process_payment
        self._payment_repo = payment_repo
        self._expected_environment = expected_environment

    async def execute(
        self,
        command: ConfirmPortOnePaymentCommand,
    ) -> ConfirmPortOnePaymentResult:
        payment = await self._payment_repo.find_by_order_id(command.payment_id)
        if payment is None or payment.provider != PaymentProvider.KG_INICIS:
            raise NotFoundException("결제 주문을 찾을 수 없습니다")
        if (
            command.expected_user_id is not None
            and payment.user_id != command.expected_user_id
        ):
            raise AuthorizationException("결제 주문에 접근할 수 없습니다")

        verified = await self._portone_gateway.get_payment(
            GetPortOnePaymentCommand(payment_id=command.payment_id)
        )
        if verified.payment_id != command.payment_id:
            raise BusinessRuleException("포트원 결제번호가 일치하지 않습니다")
        if verified.status != "PAID":
            raise BusinessRuleException("완료되지 않은 포트원 결제입니다")
        if verified.pg_provider != "HTML5_INICIS":
            raise BusinessRuleException("KG이니시스 결제가 아닙니다")
        if verified.payment_environment != self._expected_environment:
            raise BusinessRuleException("허용되지 않은 포트원 결제 환경입니다")

        result = await self._process_payment.execute(
            ProcessVerifiedPaymentCommand(
                provider=PaymentProvider.KG_INICIS,
                external_event_id=verified.transaction_id,
                event_type="PAID",
                order_id=verified.payment_id,
                provider_payment_id=verified.payment_id,
                provider_transaction_id=verified.transaction_id,
                amount=verified.amount,
                currency=verified.currency,
                approved_at=verified.paid_at,
                payment_environment=verified.payment_environment,
                payload={
                    "status": verified.status,
                    "pg_provider": verified.pg_provider,
                    "payment_environment": verified.payment_environment.value,
                },
            )
        )
        return ConfirmPortOnePaymentResult(
            payment_id=result.payment_id,
            status=result.status,
            already_processed=result.already_processed,
            test_payment=verified.payment_environment == PaymentEnvironment.TEST,
        )
