import os
import sys
import types
import unittest
from importlib.util import find_spec
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
os.environ.setdefault("R2_UPLOAD_BUCKET_NAME", "gifgloo-upload-test")
os.environ.setdefault("R2_PUBLIC_URL", "http://localhost:9000/gifgloo-test")

if find_spec("aioboto3") is None:
    sys.modules["aioboto3"] = types.SimpleNamespace(Session=lambda: None)
if find_spec("botocore") is None:
    botocore_module = types.ModuleType("botocore")
    botocore_exceptions = types.ModuleType("botocore.exceptions")
    botocore_exceptions.ClientError = type("ClientError", (Exception,), {})
    sys.modules["botocore"] = botocore_module
    sys.modules["botocore.exceptions"] = botocore_exceptions

from composition.adapter.inbound.fastapi.composition_internal_router import (  # noqa: E402
    router as composition_internal_router,
)
from composition.adapter.inbound.fastapi.composition_router import router as composition_router  # noqa: E402
from config.composition import (  # noqa: E402
    get_composition_status_service,
    get_pipeline_callback_service,
    get_request_composition_service,
    get_prepare_composition_upload_service,
    get_submit_composition_feedback_service,
)
from composition.domain.value_objects.composition_status import CompositionStatus  # noqa: E402
from shared.exceptions import CompositionUnavailableException  # noqa: E402
from shared.fastapi_error_handler import register_error_handlers  # noqa: E402
from shared.metrics import normalized_path  # noqa: E402


class _RequestCompositionResult:
    composition_job_id = "job-1"


class _RequestCompositionService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command
        return _RequestCompositionResult()


class _UnavailableCompositionService:
    async def execute(self, command):
        raise CompositionUnavailableException("잠시 후 다시 시도해 주세요", retry_after_seconds=42)


class _PrepareUploadService:
    async def execute(self, command):
        return SimpleNamespace(
            upload_id="upload-1",
            upload_url="https://uploads.example/signed",
            headers={"Content-Type": command.content_type},
            expires_in_seconds=600,
        )


class _PipelineCallbackService:
    def __init__(self):
        self.completed = None

    async def checkpoint(self, *args, **kwargs):
        pass

    async def reconcile_expired(self):
        pass

    async def complete(self, job_id: str, run_id: str, draft_key: str, result_key: str):
        self.completed = {
            "job_id": job_id,
            "run_id": run_id,
            "draft_key": draft_key,
            "result_key": result_key,
        }

    async def fail(self, *args, **kwargs):
        pass


class _CompositionStatusService:
    async def execute(self, query):
        return SimpleNamespace(
            composition_job_id=query.composition_job_id,
            status=CompositionStatus.COMPLETED,
            stage=None,
            result_url="https://assets.example/result.gif",
            result_asset_id="asset-1",
            failed_reason=None,
            credit_settlement=SimpleNamespace(
                balance_before=50,
                charged=10,
                refunded=0,
                balance_after=40,
            ),
        )


class _CompositionFeedbackService:
    def __init__(self):
        self.command = None

    async def execute(self, command):
        self.command = command


class CompositionRoutesTest(unittest.TestCase):
    def setUp(self):
        reconcile_patch = patch(
            "composition.adapter.inbound.fastapi.composition_router.reconcile_expired_composition_gate",
            new_callable=AsyncMock,
        )
        reconcile_patch.start()
        self.addCleanup(reconcile_patch.stop)
        self.request_service = _RequestCompositionService()
        self.callback_service = _PipelineCallbackService()
        self.status_service = _CompositionStatusService()
        self.feedback_service = _CompositionFeedbackService()
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(composition_router)
        app.include_router(composition_internal_router)
        app.dependency_overrides[get_request_composition_service] = lambda: self.request_service
        app.dependency_overrides[get_prepare_composition_upload_service] = lambda: _PrepareUploadService()
        app.dependency_overrides[get_pipeline_callback_service] = lambda: self.callback_service
        app.dependency_overrides[get_composition_status_service] = lambda: self.status_service
        app.dependency_overrides[get_submit_composition_feedback_service] = (
            lambda: self.feedback_service
        )
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
        self.assertEqual(self.request_service.command.target.data, b"image-bytes")
        self.assertTrue(self.request_service.command.acknowledge_frame_reduction)

    def test_prepares_direct_upload(self):
        self._set_auth_cookie()

        response = self.client.post(
            "/compositions/uploads",
            json={"content_type": "image/heic", "size": 1024},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["upload_id"], "upload-1")

    def test_requests_composition_from_direct_upload(self):
        self._set_auth_cookie()

        response = self.client.post(
            "/compositions/from-upload",
            json={
                "gif_url": "https://assets.example/source.gif",
                "upload_id": "0e65188c-13a0-4f08-b176-c6f62482db49",
                "acknowledge_frame_reduction": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.request_service.command.target.upload_id,
            "0e65188c-13a0-4f08-b176-c6f62482db49",
        )

    def test_submit_composition_feedback(self):
        self._set_auth_cookie()

        response = self.client.put(
            "/compositions/job-1/feedback",
            json={"satisfied": True},
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.feedback_service.command.composition_job_id, "job-1")
        self.assertEqual(self.feedback_service.command.user_id, "user-1")
        self.assertTrue(self.feedback_service.command.satisfied)

    def test_busy_composition_returns_retry_after(self):
        self._set_auth_cookie()
        self.client.app.dependency_overrides[get_request_composition_service] = _UnavailableCompositionService

        response = self.client.post(
            "/compositions",
            data={"gif_url": "https://assets.example/source.gif"},
            files={"target_file": ("target.png", b"image-bytes", "image/png")},
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "42")
        self.assertEqual(response.json()["error"], "COMPOSITION_UNAVAILABLE")

    def test_internal_complete_requires_secret_and_calls_service(self):
        response = self.client.post(
            "/internal/compositions/job-1/complete",
            json={"run_id": "run-1", "draft_key": "draft.png", "result_key": "result.gif"},
            headers={"X-Internal-Secret": os.environ["INTERNAL_SECRET"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.callback_service.completed,
            {
                "job_id": "job-1",
                "run_id": "run-1",
                "draft_key": "draft.png",
                "result_key": "result.gif",
            },
        )

    def test_status_returns_credit_summary(self):
        self._set_auth_cookie()

        response = self.client.get("/compositions/job-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["credit_settlement"],
            {
                "balance_before": 50,
                "charged": 10,
                "refunded": 0,
                "balance_after": 40,
            },
        )

    def test_internal_complete_rejects_missing_secret(self):
        response = self.client.post(
            "/internal/compositions/job-1/complete",
            json={"run_id": "run-1", "draft_key": "draft.png", "result_key": "result.gif"},
        )

        self.assertEqual(response.status_code, 403)


class MetricsPathTest(unittest.TestCase):
    def test_known_paths_keep_low_cardinality_labels(self):
        self.assertEqual(normalized_path("/credits/balance"), "/credits/balance")
        self.assertEqual(normalized_path("/payments/checkout"), "/payments/checkout")
        self.assertEqual(
            normalized_path("/payments/toss/callback"),
            "/payments/toss/callback",
        )
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
