from credit_account.application.ports.inbound.check_balance_sufficient import CheckBalanceSufficientPort, CheckBalanceSufficientCommand
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort


class CheckBalanceSufficientService(CheckBalanceSufficientPort):
    def __init__(self, credit_account_repo: CreditAccountRepositoryPort):
        self._credit_account_repo = credit_account_repo

    def execute(self, command: CheckBalanceSufficientCommand) -> bool:
        credit_account = self._credit_account_repo.find_credit_by_user_id(command.user_id)
        return credit_account.has_enough()
