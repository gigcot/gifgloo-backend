from datetime import datetime, timezone

from credit_account.application.ports.outbound.persistence.async_credit_account_repository import (
    AsyncCreditAccountRepository,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.application.ports.outbound.async_user_verification_port import (
    AsyncUserVerificationPort,
)
from credit_account.domain.value_objects.credit_source_type import CreditSourceType
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.exceptions import AuthorizationException, InvalidStateException, NotFoundException


class AsyncCreditService:
    def __init__(
        self,
        user_verification: AsyncUserVerificationPort,
        credit_account_repo: AsyncCreditAccountRepository,
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo

    async def has_enough_credit(self, user_id: str) -> bool:
        summary = await self._credit_account_repo.find_available_summary_by_user_id(
            user_id,
            datetime.now(timezone.utc),
        )
        return (
            summary is not None
            and summary.balance >= CreditAccount.composition_cost
        )

    async def deduct(self, user_id: str, job_id: str) -> None:
        if not await self._user_verification.is_active_user(user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")
        credit_account = await self._credit_account_repo.find_for_update(user_id)
        if credit_account is None:
            raise NotFoundException("이용권 계정을 찾을 수 없습니다")
        existing = await self._credit_account_repo.find_transaction_by_source(
            user_id=user_id,
            transaction_type=TransactionType.DEDUCT,
            source_type=CreditSourceType.COMPOSITION,
            source_id=job_id,
        )
        if existing is not None:
            return
        credit_account.deduct(
            source_type=CreditSourceType.COMPOSITION,
            source_id=job_id,
            now=datetime.now(timezone.utc),
        )
        await self._credit_account_repo.save(credit_account)

    async def refund(self, user_id: str, job_id: str) -> None:
        deduction = await self._credit_account_repo.find_transaction_by_source(
            user_id=user_id,
            transaction_type=TransactionType.DEDUCT,
            source_type=CreditSourceType.COMPOSITION,
            source_id=job_id,
        )
        if deduction is None or deduction.credit_lot_id is None:
            raise InvalidStateException("합성 작업의 이용권 차감 이력을 찾을 수 없습니다")
        credit_account = await self._credit_account_repo.find_for_update(
            user_id,
            required_lot_id=deduction.credit_lot_id,
        )
        if credit_account is None:
            raise NotFoundException("이용권 계정을 찾을 수 없습니다")
        existing_refund = await self._credit_account_repo.find_transaction_by_source(
            user_id=user_id,
            transaction_type=TransactionType.REFUND,
            source_type=CreditSourceType.COMPOSITION,
            source_id=job_id,
        )
        if existing_refund is not None:
            return

        credit_account.refund(
            original_lot_id=deduction.credit_lot_id,
            source_type=CreditSourceType.COMPOSITION,
            source_id=job_id,
            now=datetime.now(timezone.utc),
        )
        await self._credit_account_repo.save(credit_account)
