import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from config.web_push import get_web_push_settings
from shared.exceptions import ValidationException
from tools.generate_web_push_keys import generate_env
from tools.web_push_smoke import create_app, ORIGIN


class VapidSetupTest(unittest.TestCase):
    def test_generated_pair_validates_is_private_and_never_overwrites(self):
        with tempfile.TemporaryDirectory(prefix="gifgloo-vapid-test-") as directory:
            path = Path(directory) / ".env.web-push.test"
            generate_env(path, "mailto:ops@example.test")
            original = path.read_text()
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            values = dict(line.split("=", 1) for line in original.splitlines())
            with patch.dict(os.environ, values):
                self.assertIsNone(get_web_push_settings())
                os.environ["WEB_PUSH_ENABLED"] = "true"
                settings = get_web_push_settings()
                self.assertEqual(settings.public_key, values["WEB_PUSH_PUBLIC_KEY"])
                os.environ["WEB_PUSH_PUBLIC_KEY"] = "mismatched"
                with self.assertRaises(ValidationException):
                    get_web_push_settings()
                os.environ["WEB_PUSH_PUBLIC_KEY"] = values["WEB_PUSH_PUBLIC_KEY"]
                os.environ["WEB_PUSH_SUBJECT"] = "no-contact"
                with self.assertRaises(ValidationException):
                    get_web_push_settings()
            with self.assertRaises(FileExistsError):
                generate_env(path, "mailto:ops@example.test")
            self.assertEqual(path.read_text(), original)


class LocalPushSmokeTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(), base_url=ORIGIN)
        self.addCleanup(self.client.close)
        key = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        self.body = {"endpoint": "https://fcm.googleapis.com/push/test", "keys": {
            "p256dh": base64.urlsafe_b64encode(key).decode().rstrip("="),
            "auth": base64.urlsafe_b64encode(b"0" * 16).decode().rstrip("="),
        }}

    def prepare(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        return {"Origin": ORIGIN, "X-Smoke-Token": self.client.get("/config").json()["csrf"]}

    def test_serves_real_worker_without_automatic_send_and_limits_origin(self):
        with patch("tools.web_push_smoke.WebPushAdapter.send", new_callable=AsyncMock) as push:
            self.assertEqual(self.client.get("/config").status_code, 401)
            self.prepare()
            response = self.client.get("/completion-notifications-sw.js")
            self.assertEqual(response.status_code, 200)
            self.assertIn("notificationclick", response.text)
            self.assertEqual(self.client.get("/icon.png").status_code, 200)
            self.assertEqual(self.client.get("/status").json()["status"], "idle")
            self.assertEqual(self.client.get("/", headers={"Host": "evil.test"}).status_code, 403)
            self.assertEqual(self.client.post("/send", json=self.body).status_code, 403)
            push.assert_not_awaited()

    def test_click_sends_once_with_mock_transport_and_private_return(self):
        headers = self.prepare()
        with patch("tools.web_push_smoke.asyncio.sleep", new_callable=AsyncMock), patch(
            "tools.web_push_smoke.WebPushAdapter.send", new_callable=AsyncMock, return_value="accepted"
        ) as push:
            self.assertEqual(self.client.post("/send", headers=headers, json=self.body).status_code, 202)
            self.assertEqual(self.client.post("/send", headers=headers, json=self.body).status_code, 409)
            push.assert_awaited_once()
            job_id = push.call_args.args[0].job_id
            self.assertEqual(self.client.get(f"/my-assets?job={job_id}").status_code, 200)
            self.assertEqual(self.client.get("/my-assets?job=other").status_code, 404)
            self.client.cookies.clear()
            self.assertEqual(self.client.get(f"/my-assets?job={job_id}").status_code, 401)

    def test_bad_endpoint_or_cross_origin_does_not_send(self):
        headers = self.prepare()
        with patch("tools.web_push_smoke.WebPushAdapter.send", new_callable=AsyncMock) as push:
            self.assertEqual(self.client.post("/send", headers={**headers, "Origin": "https://evil.test"}, json=self.body).status_code, 403)
            self.body["endpoint"] = "https://127.0.0.1/private"
            self.assertEqual(self.client.post("/send", headers=headers, json=self.body).status_code, 422)
            push.assert_not_awaited()
