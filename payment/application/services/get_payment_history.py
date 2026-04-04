from payment.application.ports.inbound.get_payment_history import GetPaymentHistoryPort, GetPaymentHistoryCommand, GetPaymentHistoryResult
from payment.application.ports.outbound.persistence.payment_repository_port import PaymentRepositoryPort
from payment.application.ports.outbound.user_verification_port import UserVerificationPort
from shared.exceptions import AuthorizationException


class GetPaymentHistoryService(GetPaymentHistoryPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            payment_repo: PaymentRepositoryPort,
    ):
        self._user_verification = user_verification
        self._payment_repo = payment_repo

    def execute(self, command: GetPaymentHistoryCommand) -> GetPaymentHistoryResult:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")
        
        payments = self._payment_repo.find_payment_by_user_id(command.user_id)

        return GetPaymentHistoryResult(payments)

