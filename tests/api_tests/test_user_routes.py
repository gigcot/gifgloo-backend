import os
import unittest
from types import SimpleNamespace

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test",
)
os.environ.setdefault(
    "ASYNC_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
os.environ.setdefault("COOKIE_SECURE", "false")

from config.user import (  # noqa: E402
    get_record_signup_consent_service,
    get_review_login_service,
    get_user_service,
)
from user.adapter.inbound.fastapi.oauth2 import router as oauth_router  # noqa: E402
from user.adapter.inbound.fastapi.user_router import router  # noqa: E402


class FakeRecordSignupConsentService:
    def __init__(self):
        self.command = None

    def execute(self, command):
        self.command = command
        return SimpleNamespace(
            terms_version=command.terms_version,
            privacy_version=command.privacy_version,
            is_fourteen_or_older=command.is_fourteen_or_older,
            agreed_at="2026-08-09T12:00:00+00:00",
        )


class FakeGetUserService:
    def __init__(self, email="member@example.com"):
        self.email = email
        self.query = None

    def execute(self, query):
        self.query = query
        return SimpleNamespace(email=self.email)


class UserRoutesTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeRecordSignupConsentService()
        self.get_user_service = FakeGetUserService()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[
            get_record_signup_consent_service
        ] = lambda: self.service
        app.dependency_overrides[get_user_service] = lambda: self.get_user_service
        self.client = TestClient(app)

    def _set_auth_cookie(self):
        token = jwt.encode(
            {"user_id": "user-1"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        self.client.cookies.set("user_token", token)

    def test_records_signup_consent_for_authenticated_user(self):
        self._set_auth_cookie()

        response = self.client.post(
            "/users/me/consents",
            json={
                "terms_version": "2026-08-09",
                "privacy_version": "2026-08-09",
                "is_fourteen_or_older": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.service.command.user_id, "user-1")
        self.assertEqual(response.json()["terms_version"], "2026-08-09")

    def test_rejects_signup_consent_without_authentication(self):
        response = self.client.post(
            "/users/me/consents",
            json={
                "terms_version": "2026-08-09",
                "privacy_version": "2026-08-09",
                "is_fourteen_or_older": True,
            },
        )

        self.assertEqual(response.status_code, 401)

    def test_returns_saved_email_for_authenticated_user(self):
        self._set_auth_cookie()

        response = self.client.get("/users/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "email": "member@example.com"})
        self.assertEqual(self.get_user_service.query.user_id, "user-1")

    def test_returns_null_when_authenticated_user_has_no_email(self):
        self._set_auth_cookie()
        self.get_user_service.email = None

        response = self.client.get("/users/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "email": None})

    def test_rejects_existing_review_session_when_review_login_is_disabled(self):
        token = jwt.encode(
            {"user_id": "review-user", "review_login": True},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        self.client.cookies.set("user_token", token)
        os.environ["PG_REVIEW_LOGIN_ENABLED"] = "false"

        response = self.client.get("/users/me")

        self.assertEqual(response.status_code, 401)


class FakeReviewLoginService:
    def __init__(self):
        self.command = None

    def execute(self, command):
        self.command = command
        return SimpleNamespace(user_id="review-user")


class ReviewLoginRoutesTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeReviewLoginService()
        app = FastAPI()
        app.include_router(oauth_router)
        app.dependency_overrides[get_review_login_service] = lambda: self.service
        self.client = TestClient(app)

    def test_sets_user_cookie_after_review_login(self):
        response = self.client.post(
            "/oauth/review-login",
            json={"login_id": "kg-review", "password": "review-password"},
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.service.command.login_id, "kg-review")
        token = self.client.cookies.get("user_token")
        payload = jwt.decode(
            token,
            os.environ["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        self.assertEqual(payload["user_id"], "review-user")
        self.assertTrue(payload["review_login"])
