from credit_account.application.ports.outbound.user_verification_port import UserVerificationPort
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort
from credit_account.application.ports.inbound.deduct import DeductCreditCommand, DeductCreditPort
from shared.exceptions import AuthorizationException


class DeductCreditService(DeductCreditPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            credit_account_repo: CreditAccountRepositoryPort
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo

    def execute(self, command: DeductCreditCommand) -> None:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        credit_account = self._credit_account_repo.find_credit_by_user_id(command.user_id)

        credit_account.deduct()

        self._credit_account_repo.save(credit_account)