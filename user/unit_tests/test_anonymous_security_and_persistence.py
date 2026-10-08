import importlib
import io
import os
import unittest
import jwt
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")

from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from credit_account.adapter.outbound.models import CreditAccountModel, CreditLotModel, CreditTransactionModel
from credit_account.adapter.outbound.sql_alchemy_credit_account_repository import SqlAlchemyCreditAccountRepository
from credit_account.application.services.create_credit_account_service import CreateCreditAccountService
from shared.exceptions import AuthenticationException
from shared.fastapi_error_handler import register_error_handlers
from user.adapter.inbound.fastapi import oauth2, session_middleware
from user.adapter.inbound.fastapi.session import issue_session_token
from user.adapter.outbound.domain_bridges.credit_account_init_adapter import CreditAccountInitAdapter
from user.adapter.outbound.persistence.models import UserModel
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.adapter.outbound.persistence.sqlalchemy_user_transaction import SqlAlchemyUserTransaction
from user.application.ports.inbound.anonymous_session import AnonymousSessionCommand
from user.application.ports.inbound.social_login import SocialLoginCommand
from user.application.ports.outbound.social_provider_port import SocialUserInfo
from user.application.services.create_anonymous_session_service import CreateAnonymousSessionService
from user.application.services.social_login_service import SocialLoginService
from user.application.services.verify_session_service import VerifiedSessionResult
from user.domain.aggregates.user import User
from user.domain.value_objects.signup_consent import CURRENT_PRIVACY_VERSION, CURRENT_TERMS_VERSION, SignupConsent
from user.domain.value_objects.social_account import SocialAccount, SocialProvider


class AnonymousPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        for model in (UserModel, CreditAccountModel, CreditLotModel, CreditTransactionModel):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.users = SqlAlchemyUserRepository(self.db, commit_on_save=False)
        self.credits = SqlAlchemyCreditAccountRepository(self.db, commit_on_save=False)
        self.credit_init = CreditAccountInitAdapter(CreateCreditAccountService(self.credits))
        self.transaction = SqlAlchemyUserTransaction(self.db)
        # SQLite verifies actual flush/commit/rollback; PostgreSQL advisory locking is separate.
        self.transaction.lock = Mock()
        self.service = CreateAnonymousSessionService(self.users, self.credit_init, self.transaction)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_credit_failure_leaves_no_user_or_partial_grant(self):
        original = self.credit_init.init_account

        def fail_after_flush(user_id):
            original(user_id)
            raise AuthenticationException("injected failure")

        self.credit_init.init_account = fail_after_flush
        with self.assertRaises(AuthenticationException):
            self.service.execute(AnonymousSessionCommand("anon"))
        self.db.expire_all()
        for model in (UserModel, CreditAccountModel, CreditLotModel, CreditTransactionModel):
            self.assertEqual(self.db.scalars(select(model)).all(), [])

    def test_retry_and_upgrade_persist_one_identity_one_initial_grant(self):
        self.service.execute(AnonymousSessionCommand("anon"))
        self.service.execute(AnonymousSessionCommand("anon"))
        provider = Mock()
        provider.get_user_info.return_value = SocialUserInfo(SocialProvider.GOOGLE, "g", None)
        login = SocialLoginService(provider, self.users, self.credit_init, self.transaction)
        login.execute(SocialLoginCommand(
            SocialProvider.GOOGLE, "code", SignupConsent.record(CURRENT_TERMS_VERSION, CURRENT_PRIVACY_VERSION, True),
            anonymous_user_id="anon", anonymous_session_version=0,
        ))
        self.db.expire_all()
        user = self.users.find_by_id("anon")
        self.assertEqual(user.user_kind, "member")
        self.assertEqual(user.session_version, 1)
        self.assertFalse(user.consent_required)
        self.assertEqual(len(self.db.scalars(select(UserModel)).all()), 1)
        self.assertEqual(len(self.db.scalars(select(CreditLotModel)).all()), 1)
        self.assertEqual(self.db.get(CreditAccountModel, "anon").balance, 20)

    def test_multiple_anonymous_users_allowed_but_duplicate_social_account_rejected(self):
        self.service.execute(AnonymousSessionCommand("anon-1"))
        self.service.execute(AnonymousSessionCommand("anon-2"))
        self.users.save(User(SocialAccount(SocialProvider.GOOGLE, "g")))
        with self.assertRaises(IntegrityError):
            self.users.save(User(SocialAccount(SocialProvider.GOOGLE, "g")))
        self.db.rollback()

    def test_postgres_migration_generates_non_destructive_upgrade_sql(self):
        migration = importlib.import_module("migrations.versions.202610050001_anonymous_users")
        output = io.StringIO()
        context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
        with patch.object(migration, "op", Operations(context)):
            migration.upgrade()
        sql = output.getvalue()
        self.assertIn("provider DROP NOT NULL", sql)
        self.assertIn("session_version INTEGER DEFAULT '0' NOT NULL", sql)
        self.assertIn("UNIQUE (provider, provider_id)", sql)
        self.assertNotIn("DELETE", sql)
        self.assertNotIn("DROP TABLE", sql)


class AnonymousSessionMiddlewareTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.add_middleware(session_middleware.UserSessionMiddleware)

        @app.api_route("/{path:path}", methods=["GET", "POST"])
        def endpoint(path: str):
            return {"reached": path}

        @asynccontextmanager
        async def fake_db():
            yield Mock()

        self.db_patch = patch.object(session_middleware, "AsyncSessionLocal", fake_db)
        self.db_patch.start()
        self.verify = patch.object(session_middleware.VerifySessionService, "execute", new_callable=AsyncMock)
        self.execute = self.verify.start()
        self.execute.return_value = VerifiedSessionResult("anonymous", True)
        self.client = TestClient(app)
        self.client.cookies.set("user_token", issue_session_token("anon", "anonymous", 0))

    def tearDown(self):
        self.client.close()
        self.verify.stop()
        self.db_patch.stop()

    def test_anonymous_requires_consent_but_can_view_results_and_submit_survey(self):
        for path in ("/compositions", "/compositions/uploads", "/compositions/from-upload"):
            response = self.client.post(path)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["error"], "CONSENT_REQUIRED")
        for path in ("/users/me/consents", "/experiments/exp-001/survey", "/assets/result/share"):
            self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual(self.client.get("/assets/result/download").status_code, 200)
        self.execute.return_value = VerifiedSessionResult("anonymous", False)
        self.assertEqual(self.client.post("/compositions/from-upload").status_code, 200)

    def test_member_only_routes_do_not_become_anonymous_routes(self):
        for path in ("/payments/orders", "/admin/users"):
            self.assertEqual(self.client.post(path).status_code, 403)
        self.execute.return_value = VerifiedSessionResult("member", False)
        self.assertEqual(self.client.post("/payments/orders").status_code, 200)

    def test_revoked_anonymous_token_is_rejected_before_resource_handler(self):
        self.execute.side_effect = AuthenticationException("upgraded")
        response = self.client.get("/assets/result/download")
        self.assertEqual(response.status_code, 401)
        self.assertIn("Max-Age=0", response.headers["set-cookie"])
        self.assertEqual(self.client.get("/assets/shared/public").status_code, 200)

    def test_legacy_tokens_are_only_accepted_for_existing_members(self):
        token = jwt.encode({"user_id": "legacy"}, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
        self.client.cookies.set("user_token", token)
        self.assertEqual(self.client.get("/users/me").status_code, 401)
        self.client.cookies.clear()
        self.client.cookies.set("user_token", token)
        self.execute.return_value = VerifiedSessionResult("member", False)
        self.assertEqual(self.client.get("/users/me").status_code, 200)


class AnonymousOAuthBindingTest(unittest.TestCase):
    def test_oauth_state_cannot_upgrade_another_browser_identity(self):
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(oauth2.router)
        with patch.dict(os.environ, {"COOKIE_SECURE": "false"}), TestClient(app) as client:
            client.cookies.set("user_token", issue_session_token("anon-a", "anonymous", 0))
            response = client.post("/oauth/google/start", json={
                "terms_version": CURRENT_TERMS_VERSION, "privacy_version": CURRENT_PRIVACY_VERSION,
                "is_fourteen_or_older": True, "agreed_to_terms": True, "agreed_to_privacy": True,
            })
            state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
            client.cookies.set("user_token", issue_session_token("anon-b", "anonymous", 0))
            # Context validation precedes any social provider request.
            response = client.get(f"/oauth/google/callback?state={state}&code=unused", follow_redirects=False)
            self.assertEqual(response.status_code, 401)
