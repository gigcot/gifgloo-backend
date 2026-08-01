import os
import sys
import types
import unittest
from importlib.util import find_spec

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
os.environ.setdefault("INTERNAL_SECRET", "test-internal-secret")
os.environ.setdefault("R2_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("R2_BUCKET_NAME", "gifgloo-test")
os.environ.setdefault("R2_PUBLIC_URL", "http://localhost:9000/gifgloo-test")

if find_spec("aioboto3") is None:
    sys.modules["aioboto3"] = types.SimpleNamespace(Session=lambda: None)

from composition.adapter.inbound.fastapi.composition_internal_router import (  # noqa: E402
    router as composition_internal_router,
)
from composition.adapter.inbound.fastapi.composition_router import router as composition_router  # noqa: E402
from config.composition import get_pipeline_callback_service, get_request_composition_service  # noqa: E402
from shared.metrics import normalized_path  # noqa: E402


class _RequestCompositionResult:
    composition_job_id = "job-1"


class _RequestCompositionService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        return _RequestCompositionResult()


class _PipelineCallbackService:
    def __init__(self):
        self.completed = None

    async def checkpoint(self, *args, **kwargs):
        pass

    async def complete(self, job_id: str, draft_key: str, result_key: str):
        self.completed = {
            "job_id": job_id,
            "draft_key": draft_key,
            "result_key": result_key,
        }

    async def fail(self, *args, **kwargs):
        pass


class CompositionRoutesTest(unittest.TestCase):
    def setUp(self):
        self.request_service = _RequestCompositionService()
        self.callback_service = _PipelineCallbackService()
        app = FastAPI()
        app.include_router(composition_router)
        app.include_router(composition_internal_router)
        app.dependency_overrides[get_request_composition_service] = lambda: self.request_service
        app.dependency_overrides[get_pipeline_callback_service] = lambda: self.callback_service
        self.client = TestClient(app)

    def _set_auth_cookie(self) -> None:
        token = jwt.encode({"user_id": "user-1"}, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
        self.client.cookies.set("user_token", token)

    def test_request_composition_accepts_form_upload(self):
        self._set_auth_cookie()

        response = self.client.post(
            "/compositions",
            data={
                "gif_url": "https://assets.example/source.gif",
                "acknowledge_frame_reduction": "true",
            },
            files={"target_file": ("target.png", b"image-bytes", "image/png")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"composition_job_id": "job-1"})
        self.assertEqual(self.request_service.command.user_id, "user-1")
        self.assertEqual(self.request_service.command.gif_url, "https://assets.example/source.gif")
        self.assertEqual(self.request_service.command.target_bytes, b"image-bytes")
        self.assertTrue(self.request_service.command.acknowledge_frame_reduction)

    def test_internal_complete_requires_secret_and_calls_service(self):
        response = self.client.post(
            "/internal/compositions/job-1/complete",
            json={"draft_key": "draft.png", "result_key": "result.gif"},
            headers={"X-Internal-Secret": os.environ["INTERNAL_SECRET"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.callback_service.completed,
            {
                "job_id": "job-1",
                "draft_key": "draft.png",
                "result_key": "result.gif",
            },
        )

    def test_internal_complete_rejects_missing_secret(self):
        response = self.client.post(
            "/internal/compositions/job-1/complete",
            json={"draft_key": "draft.png", "result_key": "result.gif"},
        )

        self.assertEqual(response.status_code, 403)


class MetricsPathTest(unittest.TestCase):
    def test_known_paths_keep_low_cardinality_labels(self):
        self.assertEqual(normalized_path("/credits/balance"), "/credits/balance")
        self.assertEqual(
            normalized_path("/compositions/job-1/status"),
            "/compositions/{composition_job_id}/status",
        )
        self.assertEqual(
            normalized_path("/internal/compositions/job-1/fail"),
            "/internal/compositions/{job_id}/fail",
        )
        self.assertEqual(normalized_path("/assets/asset-1"), "/assets/{asset_id}")

    def test_unknown_paths_share_one_metrics_label(self):
        self.assertEqual(normalized_path("/"), "/unknown")
        self.assertEqual(normalized_path("/.env"), "/unknown")
        self.assertEqual(normalized_path("/x.php"), "/unknown")
        self.assertEqual(
            normalized_path("/wp-content/plugins/hellopress/wp_filemanager.php"),
            "/unknown",
        )
