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

from config.user import get_record_signup_consent_service  # noqa: E402
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


class UserRoutesTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeRecordSignupConsentService()
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[
            get_record_signup_consent_service
        ] = lambda: self.service
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
