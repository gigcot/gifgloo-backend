from credit_account.application.ports.outbound.user_verification_port import UserVerificationPort
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort
from credit_account.application.ports.inbound.get_balance import GetCreditBalanceCommand, GetCreditBalancePort, GetCreditBalanceResult
from shared.exceptions import AuthorizationException


class GetCreditBalanceService(GetCreditBalancePort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            credit_account_repo: CreditAccountRepositoryPort
    ):
        self._user_verification = user_verification
        self._credit_account_repo = credit_account_repo

    def execute(self, command: GetCreditBalanceCommand) -> GetCreditBalanceResult:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        credit_account = self._credit_account_repo.find_credit_by_user_id(command.user_id)

        return GetCreditBalanceResult(credit_account.balance)