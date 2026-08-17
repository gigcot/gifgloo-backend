import unittest

from argon2 import PasswordHasher

from shared.exceptions import (
    AuthenticationException,
    BusinessRuleException,
    NotFoundException,
)
from user.adapter.outbound.persistence.mock.in_memory_user_repository import (
    InMemoryUserRepository,
)
from user.application.ports.inbound.record_signup_consent import (
    RecordSignupConsentCommand,
)
from user.application.ports.inbound.review_login import ReviewLoginCommand
from user.application.services.record_signup_consent_service import (
    RecordSignupConsentService,
)
from user.application.services.review_login_service import ReviewLoginService
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


class FakeCreditAccountInit:
    def __init__(self):
        self.user_ids = []

    def init_account(self, user_id: str) -> None:
        self.user_ids.append(user_id)


class ReviewLoginServiceTest(unittest.TestCase):
    def setUp(self):
        self.repo = InMemoryUserRepository()
        self.credit_account_init = FakeCreditAccountInit()
        self.login_id = "kg-review"
        self.password = "review-password"
        self.service = ReviewLoginService(
            enabled=True,
            login_id=self.login_id,
            password_hash=PasswordHasher().hash(self.password),
            user_repo=self.repo,
            credit_account_init=self.credit_account_init,
        )

    def _command(self, **overrides):
        values = {
            "login_id": self.login_id,
            "password": self.password,
        }
        values.update(overrides)
        return ReviewLoginCommand(**values)

    def test_creates_review_user_and_credit_account_on_first_login(self):
        result = self.service.execute(self._command())

        user = self.repo.find_by_id(result.user_id)
        self.assertEqual(user.social_account.provider, SocialProvider.REVIEW)
        self.assertEqual(user.social_account.provider_id, self.login_id)
        self.assertEqual(user.signup_consent.terms_version, CURRENT_TERMS_VERSION)
        self.assertEqual(self.credit_account_init.user_ids, [user.id])

    def test_reuses_existing_review_user(self):
        first = self.service.execute(self._command())
        second = self.service.execute(self._command())

        self.assertEqual(second.user_id, first.user_id)
        self.assertEqual(self.credit_account_init.user_ids, [first.user_id])

    def test_rejects_wrong_password(self):
        with self.assertRaises(AuthenticationException):
            self.service.execute(self._command(password="wrong-password"))

    def test_rejects_login_when_disabled(self):
        service = ReviewLoginService(
            enabled=False,
            login_id=self.login_id,
            password_hash="",
            user_repo=self.repo,
            credit_account_init=self.credit_account_init,
        )

        with self.assertRaises(AuthenticationException):
            service.execute(self._command())
