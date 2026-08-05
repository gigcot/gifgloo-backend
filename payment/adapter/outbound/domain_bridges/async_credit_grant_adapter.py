from credit_account.application.ports.inbound.grant_payment_credit import (
    GrantPaymentCreditCommand as CreditCommand,
)
from credit_account.application.services.grant_payment_credit_service import (
    GrantPaymentCreditService,
)
from payment.application.ports.outbound.domain_bridges.credit_grant_port import (
    CreditGrantPort,
    GrantPaymentCreditCommand,
    GrantPaymentCreditResult,
)


class AsyncCreditGrantAdapter(CreditGrantPort):
    def __init__(self, service: GrantPaymentCreditService):
        self._service = service

    async def grant(
        self,
        command: GrantPaymentCreditCommand,
    ) -> GrantPaymentCreditResult:
        result = await self._service.execute(
            CreditCommand(
                user_id=command.user_id,
                amount=command.amount,
                payment_id=command.payment_id,
            )
        )
        return GrantPaymentCreditResult(granted=result.granted)
