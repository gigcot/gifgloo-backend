from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from credit_account.application.ports.inbound.check_balance_sufficient import CheckBalanceSufficientPort, CheckBalanceSufficientCommand
from credit_account.application.ports.inbound.deduct import DeductCreditPort, DeductCreditCommand
from credit_account.application.ports.inbound.refund import RefundCreditPort, RefundCreditCommand


class CreditAdapter(CreditPort):
    def __init__(
        self,
        check_balance_service: CheckBalanceSufficientPort,
        deduct_service: DeductCreditPort,
        refund_service: RefundCreditPort,
    ):
        self._check_balance = check_balance_service
        self._deduct = deduct_service
        self._refund = refund_service

    def has_enough_credit(self, user_id: str) -> bool:
        return self._check_balance.execute(CheckBalanceSufficientCommand(user_id=user_id))

    def deduct(self, user_id: str) -> None:
        self._deduct.execute(DeductCreditCommand(user_id=user_id))

    def refund(self, user_id: str) -> None:
        self._refund.execute(RefundCreditCommand(user_id=user_id))
