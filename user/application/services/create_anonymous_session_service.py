from shared.exceptions import AuthenticationException
from user.application.ports.inbound.anonymous_session import AnonymousSessionCommand, AnonymousSessionResult
from user.application.ports.outbound.domain_bridges.credit_account_init_port import CreditAccountInitPort
from user.application.ports.outbound.transaction import UserTransaction
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.aggregates.user import User


class CreateAnonymousSessionService:
    def __init__(self, user_repo: UserRepositoryPort, credit_init: CreditAccountInitPort, transaction: UserTransaction):
        self._users = user_repo
        self._credit = credit_init
        self._transaction = transaction

    def execute(self, command: AnonymousSessionCommand) -> AnonymousSessionResult:
        try:
            self._transaction.lock(f"user:{command.user_id}")
            user = self._users.find_by_id(command.user_id)
            created = user is None
            if user is None:
                user = User(acquisition=command.acquisition)
                user.id = command.user_id
                self._users.save(user)
                self._credit.init_account(user.id)
            elif user.user_kind != "anonymous" or not user.is_active():
                raise AuthenticationException("익명 세션을 다시 준비해주세요")
            self._transaction.commit()
            return AnonymousSessionResult(user.id, created, user.session_version)
        except Exception:
            self._transaction.rollback()
            raise
