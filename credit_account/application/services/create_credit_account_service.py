from credit_account.application.ports.inbound.create_account import CreateCreditAccountCommand, CreateCreditAccountPort
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.credit_policy import CreditPolicy


class CreateCreditAccountService(CreateCreditAccountPort):
    def __init__(self, credit_account_repo: CreditAccountRepositoryPort):
        self._credit_account_repo = credit_account_repo

    def execute(self, command: CreateCreditAccountCommand) -> None:
        account = CreditAccount(user_id=command.user_id, balance=0, transactions=[])
        account.charge(CreditPolicy.WELCOME_CREDIT)
        self._credit_account_repo.save(account)
