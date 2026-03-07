from sqlalchemy.orm import Session
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort
from credit_account.domain.aggregates.credit_account import CreditAccount


class SqlAlchemyCreditAccountRepository(CreditAccountRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, input: CreditAccount) -> None:
        raise NotImplementedError

    def find_credit_by_user_id(self, user_id: str) -> CreditAccount:
        raise NotImplementedError
