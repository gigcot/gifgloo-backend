from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.application.services.verify_user_service import VerifyUserService
from credit_account.adapter.outbound.sql_alchemy_credit_account_repository import SqlAlchemyCreditAccountRepository
from credit_account.adapter.outbound.user_verification import UserVerificationAdapter
from credit_account.application.services.get_credit_balance_service import GetCreditBalanceService


def get_credit_balance_service(db: Session = Depends(get_db)) -> GetCreditBalanceService:
    return GetCreditBalanceService(
        user_verification=UserVerificationAdapter(VerifyUserService(SqlAlchemyUserRepository(db))),
        credit_account_repo=SqlAlchemyCreditAccountRepository(db),
    )
