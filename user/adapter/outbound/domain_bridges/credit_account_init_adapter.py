from credit_account.application.ports.inbound.create_account import CreateCreditAccountCommand, CreateCreditAccountPort
from user.application.ports.outbound.domain_bridges.credit_account_init_port import CreditAccountInitPort


class CreditAccountInitAdapter(CreditAccountInitPort):
    def __init__(self, create_credit_account_service: CreateCreditAccountPort):
        self._service = create_credit_account_service

    def init_account(self, user_id: str) -> None:
        self._service.execute(CreateCreditAccountCommand(user_id=user_id))
