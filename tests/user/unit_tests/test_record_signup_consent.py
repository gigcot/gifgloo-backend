import unittest

from shared.exceptions import BusinessRuleException, NotFoundException
from user.adapter.outbound.persistence.mock.in_memory_user_repository import (
    InMemoryUserRepository,
)
from user.application.ports.inbound.record_signup_consent import (
    RecordSignupConsentCommand,
)
from user.application.services.record_signup_consent_service import (
    RecordSignupConsentService,
)
from user.domain.aggregates.user import User
from user.domain.value_objects.signup_consent import (
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
)
from user.domain.value_objects.social_account import SocialAccount, SocialProvider


class RecordSignupConsentServiceTest(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryUserRepository()
        self.user = User(
            social_account=SocialAccount(
                provider=SocialProvider.GOOGLE,
                provider_id="google-user-1",
            )
        )
        self.repo.save(self.user)
        self.service = RecordSignupConsentService(self.repo)

    def _command(self, **overrides):
        values = {
            "user_id": self.user.id,
            "terms_version": CURRENT_TERMS_VERSION,
            "privacy_version": CURRENT_PRIVACY_VERSION,
            "is_fourteen_or_older": True,
        }
        values.update(overrides)
        return RecordSignupConsentCommand(**values)

    def test_records_current_policy_versions_and_server_time(self):
        result = self.service.execute(self._command())

        self.assertEqual(result.terms_version, CURRENT_TERMS_VERSION)
        self.assertEqual(result.privacy_version, CURRENT_PRIVACY_VERSION)
        self.assertTrue(result.is_fourteen_or_older)
        self.assertIsNotNone(result.agreed_at.tzinfo)

    def test_repeated_same_consent_keeps_first_agreed_time(self):
        first = self.service.execute(self._command())
        second = self.service.execute(self._command())

        self.assertEqual(second.agreed_at, first.agreed_at)

    def test_rejects_outdated_policy_version(self):
        with self.assertRaises(BusinessRuleException):
            self.service.execute(self._command(terms_version="outdated"))

    def test_rejects_under_fourteen(self):
        with self.assertRaises(BusinessRuleException):
            self.service.execute(self._command(is_fourteen_or_older=False))

    def test_rejects_unknown_user(self):
        with self.assertRaises(NotFoundException):
            self.service.execute(self._command(user_id="missing-user"))
