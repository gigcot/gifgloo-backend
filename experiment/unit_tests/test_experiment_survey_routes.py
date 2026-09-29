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

from config.experiment import (  # noqa: E402
    get_experiment_survey_status_service,
    get_submit_experiment_survey_service,
)
from experiment.adapter.inbound.fastapi.experiment_router import router  # noqa: E402
from shared.exceptions import AuthorizationException  # noqa: E402
from shared.fastapi_error_handler import register_error_handlers  # noqa: E402


class StatusService:
    def __init__(self, eligible=True, submitted=False):
        self.eligible = eligible
        self.submitted = submitted
        self.query = None

    async def execute(self, query):
        self.query = query
        return SimpleNamespace(
            eligible=self.eligible,
            submitted=self.submitted,
        )


class SubmitService:
    def __init__(self, error=None):
        self.error = error
        self.command = None

    async def execute(self, command):
        self.command = command
        if self.error is not None:
            raise self.error
        return SimpleNamespace(submitted=True)


class ExperimentSurveyRoutesTest(unittest.TestCase):
    def setUp(self):
        self.status_service = StatusService()
        self.submit_service = SubmitService()
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(router)
        app.dependency_overrides[
            get_experiment_survey_status_service
        ] = lambda: self.status_service
        app.dependency_overrides[
            get_submit_experiment_survey_service
        ] = lambda: self.submit_service
        self.client = TestClient(app, raise_server_exceptions=False)
        token = jwt.encode(
            {"user_id": "user-1"},
            os.environ["JWT_SECRET_KEY"],
            algorithm="HS256",
        )
        self.client.cookies.set("user_token", token)

    def test_get_returns_only_eligibility_and_submission(self):
        response = self.client.get("/experiments/exp-001/survey")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"eligible": True, "submitted": False},
        )
        self.assertEqual(self.status_service.query.user_id, "user-1")

    def test_post_maps_survey_body_and_returns_submitted(self):
        response = self.client.post(
            "/experiments/exp-001/survey",
            json={
                "intended_context": "group_chat",
                "actual_actions": ["saved"],
                "non_external_use_reason": "personal_keep",
                "next_context": "친구 단톡방",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"submitted": True})
        self.assertEqual(self.submit_service.command.user_id, "user-1")
        self.assertEqual(
            self.submit_service.command.actual_actions[0].value,
            "saved",
        )

    def test_empty_actions_are_rejected_by_request_validation(self):
        response = self.client.post(
            "/experiments/exp-001/survey",
            json={
                "intended_context": "group_chat",
                "actual_actions": [],
                "non_external_use_reason": "personal_keep",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.submit_service.command)

    def test_ineligible_submission_returns_403(self):
        self.submit_service.error = AuthorizationException(
            "EXP-001 설문 대상자가 아닙니다"
        )

        response = self.client.post(
            "/experiments/exp-001/survey",
            json={
                "intended_context": "group_chat",
                "actual_actions": ["saved"],
                "non_external_use_reason": "personal_keep",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_authentication_is_required(self):
        self.client.cookies.clear()

        response = self.client.get("/experiments/exp-001/survey")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
