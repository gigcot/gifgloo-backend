from credit_account.application.ports.inbound.refund import RefundCreditPort, RefundCreditCommand
from credit_account.application.ports.outbound.persistence.credit_account_repository import CreditAccountRepositoryPort


class RefundCreditService(RefundCreditPort):
    def __init__(self, credit_account_repo: CreditAccountRepositoryPort):
        self._credit_account_repo = credit_account_repo

    def execute(self, command: RefundCreditCommand) -> None:
        credit_account = self._credit_account_repo.find_credit_by_user_id(command.user_id)
        credit_account.refund()
        self._credit_account_repo.save(credit_account)
