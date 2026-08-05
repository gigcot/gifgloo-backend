from payment.application.ports.inbound.create_payment_order import (
    CreatePaymentOrderCommand,
    CreatePaymentOrderPort,
    CreatePaymentOrderResult,
)
from payment.application.ports.outbound.domain_bridges.user_verification_port import (
    UserVerificationPort,
)
from payment.application.ports.outbound.payment_gateway.toss_pay_gateway import (
    CreateTossPayCheckoutCommand,
    TossPayGatewayPort,
)
from payment.application.ports.outbound.persistence.async_payment_repository import (
    AsyncPaymentRepository,
)
from payment.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_product import get_payment_product
from payment.domain.value_objects.payment_provider import PaymentProvider
from shared.exceptions import AuthorizationException


class CreatePaymentOrderService(CreatePaymentOrderPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        payment_repo: AsyncPaymentRepository,
        transaction: AsyncTransaction,
        toss_pay_gateway: TossPayGatewayPort,
    ):
        self._user_verification = user_verification
        self._payment_repo = payment_repo
        self._transaction = transaction
        self._toss_pay_gateway = toss_pay_gateway

    async def execute(
        self,
        command: CreatePaymentOrderCommand,
    ) -> CreatePaymentOrderResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        product = get_payment_product(command.product_id)
        payment = Payment(
            user_id=command.user_id,
            provider=PaymentProvider.TOSS_PAY,
            amount=product.amount,
            credit_amount=product.credit_amount,
            currency=product.currency,
        )
        try:
            await self._payment_repo.add(payment)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        checkout = await self._toss_pay_gateway.create_checkout(
            CreateTossPayCheckoutCommand(
                order_id=payment.order_id,
                amount=payment.amount,
                product_description=product.name,
            )
        )
        payment.assign_provider_payment(checkout.pay_token)
        try:
            await self._payment_repo.update(payment)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        return CreatePaymentOrderResult(
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            credit_amount=payment.credit_amount,
            currency=payment.currency,
            status=payment.status,
            pay_token=checkout.pay_token,
            checkout_page=checkout.checkout_page,
        )
