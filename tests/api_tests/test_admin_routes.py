import os
import unittest
from unittest.mock import patch

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["ADMIN_EMAILS"] = "admin@example.com"
os.environ["ADMIN_PANEL_PATH"] = "/admin"
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test",
)
os.environ.setdefault(
    "ASYNC_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test",
)
os.environ["JWT_SECRET_KEY"] = "test-secret-key-with-at-least-32-bytes"

from admin.adapter.inbound.fastapi.admin_router import (  # noqa: E402
    get_admin_ops_service,
    router,
)
from admin.application.ports.outbound.domain_bridges.user_admin_lookup_port import (  # noqa: E402
    AdminUserResult,
)
from admin.application.services.admin_ops_service import AdminOpsService  # noqa: E402
from config.admin import get_user_admin_lookup_port  # noqa: E402


class FakeUserAdminLookup:
    def __init__(self, user: AdminUserResult | None):
        self.user = user
        self.user_id = None

    async def find_by_id(self, user_id: str) -> AdminUserResult | None:
        self.user_id = user_id
        return self.user


class AdminRoutesTest(unittest.TestCase):
    def setUp(self):
        self.user_lookup = FakeUserAdminLookup(
            AdminUserResult(
                user_id="user-1",
                email="admin@example.com",
                is_active=True,
            )
        )
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_user_admin_lookup_port] = lambda: self.user_lookup
        self.client = TestClient(app)

    def _set_auth_cookie(self):
        token = jwt.encode(
            {"user_id": "user-1"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        self.client.cookies.set("user_token", token)

    def test_admin_me_uses_user_lookup_bridge(self):
        self._set_auth_cookie()

        response = self.client.get("/admin/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "user_id": "user-1"})
        self.assertEqual(self.user_lookup.user_id, "user-1")

    def test_admin_me_rejects_non_admin_email(self):
        self.user_lookup.user = AdminUserResult(
            user_id="user-1",
            email="user@example.com",
            is_active=True,
        )
        self._set_auth_cookie()

        response = self.client.get("/admin/me")

        self.assertEqual(response.status_code, 404)

    def test_admin_ops_service_does_not_initialize_toss_gateway(self):
        with patch(
            "admin.adapter.inbound.fastapi.admin_router.make_toss_pay_gateway",
            side_effect=AssertionError("토스 게이트웨이가 초기화되면 안 됩니다"),
        ):
            service = get_admin_ops_service(object())

        self.assertIsInstance(service, AdminOpsService)
