from composition.application.ports.outbound.domain_bridges.credit_port import CreditPort
from credit_account.application.ports.inbound.get_balance import GetCreditBalancePort, GetCreditBalanceCommand
from credit_account.application.ports.inbound.deduct import DeductCreditPort, DeductCreditCommand
from credit_account.application.ports.inbound.refund import RefundCreditPort, RefundCreditCommand
from credit_account.domain.value_objects.credit_policy import CreditPolicy


class CreditAdapter(CreditPort):
    def __init__(
        self,
        get_balance_service: GetCreditBalancePort,
        deduct_service: DeductCreditPort,
        refund_service: RefundCreditPort,
    ):
        self._get_balance = get_balance_service
        self._deduct = deduct_service
        self._refund = refund_service

    def has_enough_credit(self, user_id: str) -> bool:
        result = self._get_balance.execute(GetCreditBalanceCommand(user_id=user_id))
        return result.balance >= CreditPolicy.COMPOSITION_COST

    def deduct(self, user_id: str) -> None:
        self._deduct.execute(DeductCreditCommand(user_id=user_id))

    def refund(self, user_id: str) -> None:
        self._refund.execute(RefundCreditCommand(user_id=user_id))
