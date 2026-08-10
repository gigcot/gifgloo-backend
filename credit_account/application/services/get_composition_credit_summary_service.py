from credit_account.application.ports.inbound.get_credit_summary import (
    GetCreditSummaryResult,
)
from credit_account.application.ports.outbound.persistence.async_credit_summary_reader import (
    AsyncCreditSummaryReader,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import InvalidStateException


class GetCompositionCreditSummaryService:
    def __init__(self, credit_summary_reader: AsyncCreditSummaryReader):
        self._credit_summary_reader = credit_summary_reader

    async def execute(
        self,
        user_id: str,
        job_id: str,
    ) -> GetCreditSummaryResult | None:
        transactions = await self._credit_summary_reader.find_transactions_by_source(
            user_id=user_id,
            source_type=CreditSourceType.COMPOSITION,
            source_id=job_id,
        )
        deductions = [
            transaction
            for transaction in transactions
            if transaction.transaction_type == TransactionType.DEDUCT
        ]
        if not deductions:
            return None

        first_balance_after = deductions[0].balance_after
        last_balance_after = transactions[-1].balance_after
        if first_balance_after is None or last_balance_after is None:
            raise InvalidStateException("크레딧 거래 잔액 기록이 올바르지 않습니다")

        charged = sum(transaction.amount for transaction in deductions)
        refunded = sum(
            transaction.amount
            for transaction in transactions
            if transaction.transaction_type == TransactionType.REFUND
        )
        return GetCreditSummaryResult(
            balance_before=first_balance_after + deductions[0].amount,
            charged=charged,
            refunded=refunded,
            balance_after=last_balance_after,
        )
