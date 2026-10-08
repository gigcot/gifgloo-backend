import base64
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from fastapi.testclient import TestClient
from composition.adapter.inbound.fastapi.completion_notification_router import router
from config.web_push import get_completion_notification_service, WebPushSettings
from shared.fastapi_error_handler import register_error_handlers
from shared.exceptions import NotFoundException


class CompletionNotificationApiTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        register_error_handlers(app)
        self.service = AsyncMock()
        self.service.register.return_value = "pending"
        app.dependency_overrides[get_completion_notification_service] = lambda: self.service
        self.client = TestClient(app)
        self.secret = "test-not-a-real-secret-12345678901"
        self.client.cookies.set("user_token", jwt.encode({"user_id": "anonymous", "session_version": 0}, self.secret, algorithm="HS256"))
        key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.body = {"endpoint": "https://fcm.googleapis.com/push/test", "keys": {
            "p256dh": base64.urlsafe_b64encode(key).decode().rstrip("="),
            "auth": base64.urlsafe_b64encode(b"0" * 16).decode().rstrip("="),
        }}
        self.origin = {"Origin": "https://app.example.test"}
        for context in (
            patch.dict(os.environ, {"CORS_ORIGINS": self.origin["Origin"], "JWT_SECRET_KEY": self.secret}),
            patch("composition.adapter.inbound.fastapi.completion_notification_router.get_web_push_settings", return_value=WebPushSettings("public", "private", "mailto:ops@example.test")),
        ):
            context.start()
            self.addCleanup(context.stop)
        self.addCleanup(self.client.close)

    def test_registers_anonymous_owner_and_returns_no_subscription_secrets(self):
        response = self.client.post("/compositions/job/notification", json=self.body, headers=self.origin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "pending"})
        self.service.register.assert_awaited_once_with("anonymous", "job", self.body["endpoint"], self.body["keys"]["p256dh"], self.body["keys"]["auth"])

    def test_requires_session_and_exact_origin(self):
        self.assertEqual(self.client.post("/compositions/job/notification", json=self.body).status_code, 403)
        self.assertEqual(self.client.post("/compositions/job/notification", json=self.body, headers={"Origin": "https://evil.example"}).status_code, 403)
        self.client.cookies.clear()
        self.assertEqual(self.client.post("/compositions/job/notification", json=self.body, headers=self.origin).status_code, 401)
        self.service.register.assert_not_awaited()

    def test_other_owner_maps_to_404_and_invalid_endpoint_to_422(self):
        self.service.register.side_effect = NotFoundException("합성 작업을 찾을 수 없습니다")
        self.assertEqual(self.client.post("/compositions/job/notification", json=self.body, headers=self.origin).status_code, 404)
        self.body["endpoint"] = "https://127.0.0.1/internal"
        self.assertEqual(self.client.post("/compositions/job/notification", json=self.body, headers=self.origin).status_code, 422)

    def test_disabled_config_is_not_cached_and_registration_is_rejected(self):
        with patch("composition.adapter.inbound.fastapi.completion_notification_router.get_web_push_settings", return_value=None):
            response = self.client.get("/web-push/config")
            self.assertEqual(response.json(), {"enabled": False, "public_key": None})
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(self.client.post("/compositions/job/notification", json=self.body, headers=self.origin).status_code, 503)

    def test_cancel_passes_owner_and_endpoint_and_no_body(self):
        response = self.client.request("DELETE", "/compositions/job/notification", json={"endpoint": self.body["endpoint"]}, headers=self.origin)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.service.cancel.assert_awaited_once_with("anonymous", "job", self.body["endpoint"])
