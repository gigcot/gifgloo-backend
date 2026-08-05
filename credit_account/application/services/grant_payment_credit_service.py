from credit_account.application.ports.inbound.grant_payment_credit import (
    GrantPaymentCreditCommand,
    GrantPaymentCreditPort,
    GrantPaymentCreditResult,
)
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from shared.exceptions import NotFoundException


class GrantPaymentCreditService(GrantPaymentCreditPort):
    def __init__(self, credit_account_repo: AsyncCreditAccountRepository):
        self._credit_account_repo = credit_account_repo

    async def execute(
        self,
        command: GrantPaymentCreditCommand,
    ) -> GrantPaymentCreditResult:
        credit_account = await self._credit_account_repo.find_for_update(command.user_id)
        if credit_account is None:
            raise NotFoundException("크레딧 계정을 찾을 수 없습니다")

        source_type = CreditSourceType.PAYMENT
        if await self._credit_account_repo.exists_transaction_by_source(
            source_type,
            command.payment_id,
        ):
            return GrantPaymentCreditResult(granted=False)

        credit_account.charge(
            command.amount,
            source_type=source_type,
            source_id=command.payment_id,
        )
        await self._credit_account_repo.save(credit_account)
        return GrantPaymentCreditResult(granted=True)
