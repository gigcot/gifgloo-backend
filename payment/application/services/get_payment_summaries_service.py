from payment.application.ports.inbound.get_payment_summaries import (
    GetPaymentSummariesCommand,
    GetPaymentSummariesPort,
    GetPaymentSummariesResult,
)
from payment.application.ports.outbound.persistence.async_payment_repository import (
    AsyncPaymentRepository,
)


class GetPaymentSummariesService(GetPaymentSummariesPort):
    def __init__(self, payment_repo: AsyncPaymentRepository):
        self._payment_repo = payment_repo

    async def execute(
        self,
        command: GetPaymentSummariesCommand,
    ) -> GetPaymentSummariesResult:
        payments = await self._payment_repo.find_all_by_ids_for_user(
            command.user_id,
            command.payment_ids,
        )
        return GetPaymentSummariesResult(payments=payments)
