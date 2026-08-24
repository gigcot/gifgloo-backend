from credit_account.application.ports.outbound.domain_bridges.payment_summary_port import (
    GetPaymentSummariesCommand,
    PaymentSummaryPort,
    PaymentSummaryResult,
)
from payment.application.ports.inbound.get_payment_summaries import (
    GetPaymentSummariesCommand as PaymentCommand,
)
from payment.application.services.get_payment_summaries_service import (
    GetPaymentSummariesService,
)


class AsyncPaymentSummaryAdapter(PaymentSummaryPort):
    def __init__(self, service: GetPaymentSummariesService):
        self._service = service

    async def get_summaries(
        self,
        command: GetPaymentSummariesCommand,
    ) -> list[PaymentSummaryResult]:
        result = await self._service.execute(
            PaymentCommand(
                user_id=command.user_id,
                payment_ids=command.payment_ids,
            )
        )
        return [
            PaymentSummaryResult(
                payment_id=payment.id,
                order_id=payment.order_id,
                amount=payment.amount,
                currency=payment.currency,
                credit_amount=payment.credit_amount,
                purpose=payment.purpose.value,
                status=payment.status.value,
                approved_at=payment.approved_at,
                canceled_at=payment.canceled_at,
            )
            for payment in result.payments
        ]
