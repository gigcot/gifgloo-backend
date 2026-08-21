from payment.application.ports.inbound.create_payment_order import (
    CreatePaymentOrderCommand,
    CreatePaymentOrderPort,
    CreatePaymentOrderResult,
)
from payment.application.ports.outbound.domain_bridges.user_verification_port import (
    UserVerificationPort,
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
    ):
        self._user_verification = user_verification
        self._payment_repo = payment_repo
        self._transaction = transaction

    async def execute(
        self,
        command: CreatePaymentOrderCommand,
    ) -> CreatePaymentOrderResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        try:
            product = get_payment_product(command.product_id)
            payment = Payment(
                user_id=command.user_id,
                provider=PaymentProvider.KG_INICIS,
                amount=product.amount,
                credit_amount=product.credit_amount,
                purpose=product.purpose,
                currency=product.currency,
            )
            await self._payment_repo.add(payment)
            await self._transaction.commit()
        except Exception:
            await self._transaction.rollback()
            raise

        return CreatePaymentOrderResult(
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            credit_amount=payment.credit_amount,
            purpose=payment.purpose,
            currency=payment.currency,
            status=payment.status,
            order_name=product.name,
        )
