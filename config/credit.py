from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from credit_account.adapter.outbound.async_user_verification import AsyncUserVerificationAdapter
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import (
    SqlAlchemyAsyncCreditAccountRepository,
)
from credit_account.application.services.get_credit_balance_service import GetCreditBalanceService
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import SqlAlchemyAsyncUserRepository
from user.application.services.async_verify_user_service import AsyncVerifyUserService


def get_credit_balance_service(
    db: AsyncSession = Depends(get_async_db),
) -> GetCreditBalanceService:
    return GetCreditBalanceService(
        user_verification=AsyncUserVerificationAdapter(
            AsyncVerifyUserService(SqlAlchemyAsyncUserRepository(db))
        ),
        credit_account_repo=SqlAlchemyAsyncCreditAccountRepository(db),
    )
