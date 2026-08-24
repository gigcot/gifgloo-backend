from datetime import datetime, timezone

from credit_account.application.ports.inbound.get_lot_history import (
    CreditLotHistoryItemResult,
    GetCreditLotHistoryCommand,
    GetCreditLotHistoryPort,
    GetCreditLotHistoryResult,
)
from credit_account.application.ports.outbound.async_user_verification_port import (
    AsyncUserVerificationPort,
)
from credit_account.application.ports.outbound.domain_bridges.payment_summary_port import (
    GetPaymentSummariesCommand,
    PaymentSummaryPort,
)
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from shared.exceptions import AuthorizationException, InvalidStateException


class GetCreditLotHistoryService(GetCreditLotHistoryPort):
    def __init__(
        self,
        user_verification: AsyncUserVerificationPort,
        credit_account_repo: AsyncCreditAccountRepository,
        payment_summaries: PaymentSummaryPort,
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo
        self._payment_summaries = payment_summaries

    async def execute(
        self,
        command: GetCreditLotHistoryCommand,
    ) -> GetCreditLotHistoryResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        lots = await self._credit_account_repo.find_lot_page_by_user_id(
            user_id=command.user_id,
            source_type=CreditSourceType.PAYMENT,
            limit=command.limit + 1,
            cursor_created_at=command.cursor_created_at,
            cursor_id=command.cursor_id,
        )
        has_more = len(lots) > command.limit
        page = lots[:command.limit]
        payment_ids: list[str] = []
        for lot in page:
            if lot.source_id is None:
                raise InvalidStateException("결제 이용권의 출처가 올바르지 않습니다")
            payment_ids.append(lot.source_id)

        summaries = await self._payment_summaries.get_summaries(
            GetPaymentSummariesCommand(
                user_id=command.user_id,
                payment_ids=payment_ids,
            )
        )
        summaries_by_id = {summary.payment_id: summary for summary in summaries}
        if len(summaries_by_id) != len(payment_ids):
            raise InvalidStateException("결제 이용권과 결제 내역이 일치하지 않습니다")

        now = datetime.now(timezone.utc)
        items: list[CreditLotHistoryItemResult] = []
        for lot in page:
            payment_id = lot.source_id
            if payment_id is None:
                raise InvalidStateException("결제 이용권의 출처가 올바르지 않습니다")
            payment = summaries_by_id[payment_id]
            expired = lot.is_expired(now)
            remaining_amount = lot.available_amount(now)
            items.append(
                CreditLotHistoryItemResult(
                    lot_id=lot.id,
                    payment_id=payment_id,
                    granted_amount=lot.granted_amount,
                    granted_uses=lot.granted_amount // CreditAccount.composition_cost,
                    remaining_amount=remaining_amount,
                    remaining_uses=remaining_amount // CreditAccount.composition_cost,
                    expires_at=lot.expires_at,
                    expired=expired,
                    created_at=lot.created_at,
                    order_id=payment.order_id,
                    payment_amount=payment.amount,
                    currency=payment.currency,
                    purpose=payment.purpose,
                    payment_status=payment.status,
                    approved_at=payment.approved_at,
                    canceled_at=payment.canceled_at,
                )
            )

        last = page[-1] if has_more else None
        return GetCreditLotHistoryResult(
            items=items,
            has_more=has_more,
            next_cursor_created_at=last.created_at if last else None,
            next_cursor_id=last.id if last else None,
        )
