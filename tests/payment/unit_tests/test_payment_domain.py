import unittest

from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_provider import PaymentProvider
from payment.domain.value_objects.payment_environment import PaymentEnvironment
from shared.exceptions import BusinessRuleException, InvalidStateException


class PaymentDomainTest(unittest.TestCase):
    def setUp(self):
        self.payment = Payment(
            user_id="user-1",
            provider=PaymentProvider.TOSS_PAY,
            amount=5000,
            credit_amount=100,
        )

    def test_rejects_mismatched_approval_amount(self):
        with self.assertRaises(BusinessRuleException):
            self.payment.validate_approval(
                provider=PaymentProvider.TOSS_PAY,
                amount=6000,
                currency="KRW",
            )

    def test_rejects_conflicting_provider_transaction_id(self):
        self.payment.assign_payment_environment(PaymentEnvironment.LIVE)
        self.payment.approve(
            provider_payment_id="payment-1",
            provider_transaction_id="transaction-1",
        )

        with self.assertRaises(InvalidStateException):
            self.payment.approve(
                provider_payment_id="payment-1",
                provider_transaction_id="transaction-2",
            )

    def test_grants_credit_only_for_live_payment(self):
        self.payment.assign_payment_environment(PaymentEnvironment.TEST)
        self.payment.approve()

        self.assertFalse(self.payment.can_grant_credit())

    def test_rejects_unknown_payment_environment(self):
        with self.assertRaises(BusinessRuleException):
            self.payment.assign_payment_environment(PaymentEnvironment.UNKNOWN)
