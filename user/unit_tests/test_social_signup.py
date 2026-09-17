import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

from config.user import get_google_social_login_service  # noqa: E402
from credit_account.application.services.create_credit_account_service import CreateCreditAccountService  # noqa: E402
from shared.fastapi_error_handler import register_error_handlers  # noqa: E402
from user.adapter.inbound.fastapi import oauth2  # noqa: E402
from user.application.ports.inbound.social_login import SocialLoginCommand, SocialLoginResult  # noqa: E402
from user.application.ports.outbound.social_provider_port import SocialUserInfo  # noqa: E402
from user.application.services.social_login_service import SocialLoginService  # noqa: E402
from user.domain.value_objects.signup_consent import (  # noqa: E402
    CURRENT_PRIVACY_VERSION,
    CURRENT_TERMS_VERSION,
    SignupConsent,
)
from user.domain.value_objects.social_account import SocialProvider  # noqa: E402


class OAuthSignupTest(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        register_error_handlers(self.app)
        self.app.include_router(oauth2.router)
        self.login_calls = []

        class LoginService:
            def execute(inner_self, command):
                self.login_calls.append(command)
                return SocialLoginResult(user_id="new-user", is_new_user=True)

        self.app.dependency_overrides[get_google_social_login_service] = LoginService
        self.client = TestClient(self.app)
        self.env = patch.dict(os.environ, {"COOKIE_SECURE": "false"})
        self.env.start()
        self.callback_url = patch.object(oauth2, "FRONTEND_CALLBACK_URL", "https://gifgloo.test/callback")
        self.callback_url.start()

    def tearDown(self):
        self.callback_url.stop()
        self.env.stop()
        self.client.close()

    def test_direct_oauth_call_or_missing_consent_cannot_create_user(self):
        self.assertEqual(self.client.get("/oauth/google").status_code, 404)
        consent = {
            "terms_version": CURRENT_TERMS_VERSION,
            "privacy_version": CURRENT_PRIVACY_VERSION,
            "is_fourteen_or_older": True,
            "agreed_to_terms": True,
            "agreed_to_privacy": True,
        }
        for change in (
            {"is_fourteen_or_older": False},
            {"agreed_to_terms": False},
            {"agreed_to_privacy": False},
        ):
            self.assertEqual(self.client.post("/oauth/google/start", json=consent | change).status_code, 400)
        self.assertEqual(self.client.get("/oauth/google/callback?code=code&state=fake").status_code, 401)
        self.assertEqual(self.login_calls, [])

    def test_valid_consent_is_required_through_oauth_callback(self):
        response = self.client.post("/oauth/google/start", json={
            "terms_version": CURRENT_TERMS_VERSION,
            "privacy_version": CURRENT_PRIVACY_VERSION,
            "is_fourteen_or_older": True,
            "agreed_to_terms": True,
            "agreed_to_privacy": True,
        })
        self.assertEqual(response.status_code, 200)
        state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
        self.assertEqual(self.client.get("/oauth/google/callback?code=code&state=wrong").status_code, 401)
        result = self.client.get(f"/oauth/google/callback?code=code&state={state}", follow_redirects=False)
        self.assertEqual(result.status_code, 307)
        self.assertEqual(result.headers["location"], "https://gifgloo.test/callback?is_new_user=true")
        self.assertEqual(len(self.login_calls), 1)
        self.assertTrue(self.login_calls[0].signup_consent.is_fourteen_or_older)


class SocialSignupCreditTest(unittest.TestCase):
    def test_new_user_gets_two_uses_and_returning_user_gets_no_extra_credit(self):
        class SocialProviderStub:
            def get_user_info(self, code):
                return SocialUserInfo(provider=SocialProvider.GOOGLE, provider_id="google-1", email="user@example.com")

        class UserRepo:
            user = None

            def find_by_social_account(self, social_account):
                return self.user

            def save(self, user):
                self.user = user

        class CreditRepo:
            accounts = []

            def save(self, account):
                self.accounts.append(account)

        class CreditInit:
            def __init__(self, repo):
                self.service = CreateCreditAccountService(repo)

            def init_account(self, user_id):
                from credit_account.application.ports.inbound.create_account import CreateCreditAccountCommand
                self.service.execute(CreateCreditAccountCommand(user_id=user_id))

        user_repo = UserRepo()
        credit_repo = CreditRepo()
        service = SocialLoginService(SocialProviderStub(), user_repo, CreditInit(credit_repo))
        consent = SignupConsent.record(CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION, True)
        command = SocialLoginCommand(provider=SocialProvider.GOOGLE, code="code", signup_consent=consent)

        self.assertTrue(service.execute(command).is_new_user)
        self.assertEqual(user_repo.user.signup_consent, consent)
        self.assertEqual(credit_repo.accounts[0].available_balance(), 20)
        self.assertFalse(service.execute(command).is_new_user)
        self.assertEqual(len(credit_repo.accounts), 1)


if __name__ == "__main__":
    unittest.main()
