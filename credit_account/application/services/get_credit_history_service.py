from credit_account.application.ports.inbound.get_history import (
    GetCreditHistoryCommand,
    GetCreditHistoryPort,
    GetCreditHistoryResult,
)
from credit_account.application.ports.outbound.async_user_verification_port import (
    AsyncUserVerificationPort,
)
from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import AuthorizationException


class GetCreditHistoryService(GetCreditHistoryPort):
    def __init__(
        self,
        user_verification: AsyncUserVerificationPort,
        credit_account_repo: AsyncCreditAccountRepository,
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo

    async def execute(
        self,
        command: GetCreditHistoryCommand,
    ) -> GetCreditHistoryResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        transactions = await self._credit_account_repo.find_transaction_page_by_user_id(
            user_id=command.user_id,
            transaction_types=frozenset(
                {
                    TransactionType.CHARGE,
                    TransactionType.DEDUCT,
                    TransactionType.REFUND,
                }
            ),
            limit=command.limit + 1,
            cursor_created_at=command.cursor_created_at,
            cursor_id=command.cursor_id,
        )
        has_more = len(transactions) > command.limit
        page = transactions[:command.limit]
        last = page[-1] if has_more else None
        return GetCreditHistoryResult(
            transactions=page,
            has_more=has_more,
            next_cursor_created_at=last.created_at if last else None,
            next_cursor_id=last.id if last else None,
        )
