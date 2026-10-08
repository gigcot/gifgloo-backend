import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.user import get_anonymous_session_service, get_user_service
from credit_account.application.services.create_credit_account_service import CreateCreditAccountService
from shared.exceptions import AuthenticationException
from shared.fastapi_error_handler import register_error_handlers
from shared.session_token import decode_session_token
from user.adapter.inbound.fastapi import user_router
from user.adapter.inbound.fastapi.session import BOOTSTRAP_COOKIE, issue_session_token
from user.adapter.outbound.domain_bridges.credit_account_init_adapter import CreditAccountInitAdapter
from user.adapter.outbound.persistence.mock.in_memory_user_repository import InMemoryUserRepository
from user.application.ports.inbound.anonymous_session import AnonymousSessionCommand
from user.application.ports.inbound.social_login import SocialLoginCommand
from user.application.ports.outbound.social_provider_port import SocialUserInfo
from user.application.services.create_anonymous_session_service import CreateAnonymousSessionService
from user.application.services.get_user_service import GetUserService
from user.application.services.social_login_service import SocialLoginService
from user.application.services.verify_session_service import VerifySessionService
from user.domain.aggregates.user import User
from user.domain.value_objects.acquisition import Acquisition
from user.domain.value_objects.signup_consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION, SignupConsent
from user.domain.value_objects.social_account import SocialAccount, SocialProvider


class CreditRepo:
    def __init__(self):
        self.accounts = {}
        self.saves = 0

    def save(self, account):
        self.accounts[account.user_id] = account
        self.saves += 1


class AnonymousServiceTest(unittest.TestCase):
    def setUp(self):
        self.users = InMemoryUserRepository()
        self.credits = CreditRepo()
        self.credit_init = CreditAccountInitAdapter(CreateCreditAccountService(self.credits))
        self.transaction = Mock()
        self.service = CreateAnonymousSessionService(self.users, self.credit_init, self.transaction)

    def test_creation_retry_preserves_identity_acquisition_and_single_grant(self):
        first = self.service.execute(AnonymousSessionCommand("anon", Acquisition(campaign="exp001_run01")))
        account = self.credits.accounts["anon"]
        account.deduct()
        again = self.service.execute(AnonymousSessionCommand("anon", Acquisition(campaign="changed")))
        self.assertTrue(first.created)
        self.assertFalse(again.created)
        self.assertEqual(first.user_id, again.user_id)
        self.assertEqual(self.users.find_by_id("anon").acquisition.campaign, "exp001_run01")
        self.assertEqual(account.available_balance(), 10)
        self.assertEqual(self.credits.saves, 1)

    def social_service(self):
        provider = Mock()
        provider.get_user_info.return_value = SocialUserInfo(SocialProvider.GOOGLE, "google-1", "user@example.com")
        return SocialLoginService(provider, self.users, self.credit_init, self.transaction)

    def command(self):
        return SocialLoginCommand(
            SocialProvider.GOOGLE, "code", SignupConsent.record(CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION, True),
            anonymous_user_id="anon", anonymous_session_version=0,
        )

    def test_signup_upgrades_same_id_without_credit_reset(self):
        self.service.execute(AnonymousSessionCommand("anon", Acquisition(campaign="exp001_run01")))
        account = self.credits.accounts["anon"]
        account.deduct()
        expiry = account.lots[0].expires_at
        result = self.social_service().execute(self.command())
        self.assertTrue(result.is_new_user)
        self.assertEqual(result.user_id, "anon")
        self.assertEqual(result.session_version, 1)
        self.assertEqual(account.available_balance(), 10)
        self.assertEqual(account.lots[0].expires_at, expiry)
        self.assertEqual(self.credits.saves, 1)
        self.assertEqual(self.users.find_by_id("anon").acquisition.campaign, "exp001_run01")

    def test_existing_member_does_not_merge_or_deactivate_anonymous_user(self):
        self.service.execute(AnonymousSessionCommand("anon"))
        member = User(SocialAccount(SocialProvider.GOOGLE, "google-1"))
        self.users.save(member)
        result = self.social_service().execute(self.command())
        self.assertFalse(result.is_new_user)
        self.assertEqual(result.user_id, member.id)
        self.assertTrue(self.users.find_by_id("anon").is_active())
        self.assertEqual(self.users.find_by_id("anon").user_kind, "anonymous")
        self.assertEqual(self.credits.saves, 1)

    def test_member_cannot_be_recovered_with_old_bootstrap_identity(self):
        self.service.execute(AnonymousSessionCommand("anon"))
        self.social_service().execute(self.command())
        with self.assertRaises(AuthenticationException):
            self.service.execute(AnonymousSessionCommand("anon"))

    def test_credit_failure_rolls_back_creation(self):
        self.credit_init.init_account = Mock(side_effect=AuthenticationException("failure"))
        with self.assertRaises(AuthenticationException):
            self.service.execute(AnonymousSessionCommand("anon"))
        self.transaction.rollback.assert_called_once()
        self.transaction.commit.assert_not_called()


class AnonymousSessionRouteTest(unittest.TestCase):
    def setUp(self):
        self.users = InMemoryUserRepository()
        self.credits = CreditRepo()
        credit_init = CreditAccountInitAdapter(CreateCreditAccountService(self.credits))
        self.service = CreateAnonymousSessionService(self.users, credit_init, Mock())
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(user_router.router)
        app.dependency_overrides[get_user_service] = lambda: GetUserService(self.users)
        app.dependency_overrides[get_anonymous_session_service] = lambda: self.service
        self.client = TestClient(app)
        self.env = patch.dict(os.environ, {"COOKIE_SECURE": "false"})
        self.env.start()

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_handshake_creates_once_and_persists_cookie(self):
        first = self.client.post("/users/anonymous-session", json={})
        self.assertEqual(first.status_code, 202)
        self.assertEqual(self.credits.saves, 0)
        seed = self.client.cookies[BOOTSTRAP_COOKIE]
        with self.assertRaises(jwt.InvalidTokenError):
            decode_session_token(seed, os.environ["JWT_SECRET_KEY"])
        created = self.client.post("/users/anonymous-session", json={"acquisition": {"campaign": "exp001_run01"}})
        self.assertEqual(created.status_code, 200)
        self.assertTrue(created.json()["created"])
        self.assertEqual(created.json()["user_kind"], "anonymous")
        self.assertIn("HttpOnly", created.headers["set-cookie"])
        self.assertIn("Max-Age=15552000", created.headers["set-cookie"])
        again = self.client.post("/users/anonymous-session", json={})
        self.assertFalse(again.json()["created"])
        self.assertEqual(again.json()["user_id"], created.json()["user_id"])
        self.assertEqual(self.credits.saves, 1)
        me = self.client.get("/users/me")
        self.assertTrue(me.json()["consent_required"])

    def test_lost_response_reuses_bootstrap_without_new_grant(self):
        self.client.post("/users/anonymous-session", json={})
        seed = self.client.cookies[BOOTSTRAP_COOKIE]
        first = self.client.post("/users/anonymous-session", json={})
        self.client.cookies.clear()
        self.client.cookies.set(BOOTSTRAP_COOKIE, seed)
        retry = self.client.post("/users/anonymous-session", json={})
        self.assertEqual(first.json()["user_id"], retry.json()["user_id"])
        self.assertEqual(self.credits.saves, 1)

    def test_expired_or_tampered_token_does_not_create_user(self):
        for token in ("invalid", jwt.encode({"user_id": "anon", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, os.environ["JWT_SECRET_KEY"], algorithm="HS256")):
            self.client.cookies.clear()
            self.client.cookies.set("user_token", token)
            self.assertEqual(self.client.post("/users/anonymous-session", json={}).status_code, 401)
        self.assertEqual(self.credits.saves, 0)


class SessionVersionTest(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_invalidates_old_anonymous_session(self):
        user = User()
        class Users:
            async def find_by_id(self, user_id):
                return user
        service = VerifySessionService(Users())
        self.assertEqual((await service.execute(user.id, 0)).user_kind, "anonymous")
        user.connect_social_account(SocialAccount(SocialProvider.GOOGLE, "g"), None)
        with self.assertRaises(AuthenticationException):
            await service.execute(user.id, 0)
        self.assertEqual((await service.execute(user.id, 1)).user_kind, "member")

    async def test_issued_token_has_finite_expiry_and_version(self):
        token = issue_session_token("u", "anonymous", 0)
        payload = decode_session_token(token, os.environ["JWT_SECRET_KEY"])
        self.assertGreater(payload["exp"], payload["iat"])
        self.assertEqual(payload["session_version"], 0)
