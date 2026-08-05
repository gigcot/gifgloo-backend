import unittest

from payment.domain.aggregates.payment import Payment
from payment.domain.value_objects.payment_provider import PaymentProvider
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
        self.payment.approve(
            provider_payment_id="payment-1",
            provider_transaction_id="transaction-1",
        )

        with self.assertRaises(InvalidStateException):
            self.payment.approve(
                provider_payment_id="payment-1",
                provider_transaction_id="transaction-2",
            )
