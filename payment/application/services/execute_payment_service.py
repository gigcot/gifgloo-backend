from payment.application.ports.inbound.execute_payment import ExecutePaymentPort, ExecutePaymentCommand, ExecutePaymentResult
from payment.application.ports.outbound.credit_charge_port import ChargeCreditPort
from payment.application.ports.outbound.payment_gateway.pay_by_pg import PayByPGPort
from payment.application.ports.outbound.persistence.payment_repository_port import PaymentRepositoryPort
from payment.application.ports.outbound.user_verification_port import UserVerificationPort
from payment.domain.aggregates.payment import Payment, PaymentStatus

class ExecutePaymentService(ExecutePaymentPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            payment_repo: PaymentRepositoryPort,
            payment_gateway: PayByPGPort,
            credit_charge_service: ChargeCreditPort,
    ):
        self._user_verification = user_verification
        self._payment_repo = payment_repo
        self._payment_gateway = payment_gateway
        self._credit_charge_service = credit_charge_service
    
    def execute(self, command: ExecutePaymentCommand) -> ExecutePaymentResult:
        if not self._user_verification.is_active_user(command.user_id):
            raise ValueError("유효하지 않은 유저입니다")
        
        payment = Payment(command.user_id, command.pg_type, command.amount)

        result = self._payment_gateway.pay(command.pg_type, command.amount)

        # TODO: amount 관련 정책 필요

        if result.status == PaymentStatus.COMPLETED:
            payment.complete()
            self._credit_charge_service.charge(command.user_id, ...)
            
        else:
            payment.fail(result.reason) 

        self._payment_repo.save(payment)

        return ExecutePaymentResult(result.status, result.reason or None)