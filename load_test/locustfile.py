import csv
import json
import os
import time
from json import JSONDecodeError
from itertools import cycle
from pathlib import Path

from dotenv import load_dotenv
from locust import HttpUser, between, task


load_dotenv(".env.loadtest")

import load_test.locust_pushgateway  # noqa: E402,F401

TOKEN_CSV = Path(os.environ["LOADTEST_TOKEN_OUTPUT_PATH"])
TARGET_IMAGE = Path(os.environ["LOADTEST_TARGET_IMAGE_PATH"])
GIF_URL = os.environ["LOADTEST_GIF_URL"]
PIPELINE_FAIL_MARKER = os.environ["LOADTEST_PIPELINE_FAIL_MARKER"]
HOME_PAGE_WEIGHT = int(os.environ["LOADTEST_HOME_PAGE_WEIGHT"])
COMPOSE_PAGE_WEIGHT = int(os.environ["LOADTEST_COMPOSE_PAGE_WEIGHT"])
SUCCESS_WEIGHT = int(os.environ["LOADTEST_SUCCESS_WEIGHT"])
FAIL_WEIGHT = int(os.environ["LOADTEST_FAIL_WEIGHT"])
MY_ASSETS_PAGE_WEIGHT = int(os.environ["LOADTEST_MY_ASSETS_PAGE_WEIGHT"])
CONFIRMATION_WEIGHT = (
    int(os.environ["LOADTEST_CONFIRMATION_WEIGHT"])
    if "LOADTEST_CONFIRMATION_WEIGHT" in os.environ
    else 0
)
FEASIBILITY_REJECT_WEIGHT = (
    int(os.environ["LOADTEST_FEASIBILITY_REJECT_WEIGHT"])
    if "LOADTEST_FEASIBILITY_REJECT_WEIGHT" in os.environ
    else 0
)
STATUS_TIMEOUT_SECONDS = float(os.environ["LOADTEST_STATUS_TIMEOUT_SECONDS"])
FEASIBILITY_BLOCK_MARKER = os.environ["LOADTEST_FEASIBILITY_BLOCK_MARKER"]


def _load_tokens() -> list[dict[str, str]]:
    with TOKEN_CSV.open() as token_file:
        return list(csv.DictReader(token_file))


TOKENS = _load_tokens()
TOKEN_ITERATOR = cycle(TOKENS)


class GifglooLoadTestUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        token = next(TOKEN_ITERATOR)
        self.user_id = token["user_id"]
        self.client.cookies.set("user_token", token["user_token"].strip())
        self.client.headers.update(
            {"X-Loadtest-Run-ID": os.environ.get("LOADTEST_RUN_ID", "direct")}
        )

    @task(HOME_PAGE_WEIGHT)
    def home_page_load(self) -> None:
        self.get_me(times=2)
        self.client.get("/credits/balance", name="GET /credits/balance")
        self.client.get("/compositions", name="GET /compositions")

    @task(COMPOSE_PAGE_WEIGHT)
    def compose_page_load(self) -> None:
        self.get_me(times=2)
        self.client.get("/credits/balance", name="GET /credits/balance")

    @task(SUCCESS_WEIGHT)
    def composition_success_flow(self) -> None:
        self.composition_flow(should_fail=False)

    @task(FAIL_WEIGHT)
    def composition_fail_flow(self) -> None:
        self.composition_flow(should_fail=True)

    @task(CONFIRMATION_WEIGHT)
    def composition_confirmation_flow(self) -> None:
        self.compose_page_load()
        with TARGET_IMAGE.open("rb") as target_file:
            with self.client.post(
                "/compositions",
                name="POST /compositions confirmation required",
                data={
                    "gif_url": GIF_URL,
                    "acknowledge_frame_reduction": "false",
                },
                files={"target_file": (TARGET_IMAGE.name, target_file, "image/jpeg")},
                catch_response=True,
            ) as response:
                if response.status_code != 422:
                    response.failure(f"expected 422 confirmation, got {response.status_code}")
                    return
                try:
                    body = response.json()
                except JSONDecodeError as exc:
                    response.failure(f"invalid confirmation JSON: {exc}")
                    return
                if body["error"] != "CONFIRMATION_REQUIRED":
                    response.failure(f"expected CONFIRMATION_REQUIRED, got {body['error']}")
                    return
                response.success()

        response = self.post_composition(GIF_URL, acknowledge_frame_reduction=True)
        if response.status_code != 200:
            return
        job_id = response.json()["composition_job_id"]
        self.wait_for_sse_status(job_id, "COMPLETED")
        self.client.get("/compositions", name="GET /compositions")

    @task(FEASIBILITY_REJECT_WEIGHT)
    def composition_feasibility_reject_flow(self) -> None:
        self.compose_page_load()
        with TARGET_IMAGE.open("rb") as target_file:
            with self.client.post(
                "/compositions",
                name="POST /compositions feasibility rejected",
                data={
                    "gif_url": self.feasibility_reject_gif_url(),
                    "acknowledge_frame_reduction": "true",
                },
                files={"target_file": (TARGET_IMAGE.name, target_file, "image/jpeg")},
                catch_response=True,
            ) as response:
                if response.status_code == 400:
                    response.success()
                    return
                response.failure(f"expected 400 feasibility rejection, got {response.status_code}")

    @task(MY_ASSETS_PAGE_WEIGHT)
    def my_assets_page_load(self) -> None:
        self.get_me(times=2)
        self.client.get("/credits/balance", name="GET /credits/balance")
        self.client.get("/compositions", name="GET /compositions")
        self.client.get("/assets", name="GET /assets")

    def composition_flow(self, should_fail: bool) -> None:
        self.compose_page_load()

        gif_url = self.fail_gif_url() if should_fail else GIF_URL

        response = self.post_composition(gif_url, acknowledge_frame_reduction=True)
        if response.status_code != 200:
            return

        job_id = response.json()["composition_job_id"]
        expected_status = "FAILED" if should_fail else "COMPLETED"
        self.wait_for_sse_status(job_id, expected_status)
        self.client.get("/compositions", name="GET /compositions")

    def fail_gif_url(self) -> str:
        separator = "&" if "?" in GIF_URL else "?"
        return f"{GIF_URL}{separator}loadtest={PIPELINE_FAIL_MARKER}"

    def feasibility_reject_gif_url(self) -> str:
        separator = "&" if "?" in GIF_URL else "?"
        return f"{GIF_URL}{separator}loadtest={FEASIBILITY_BLOCK_MARKER}"

    def get_me(self, times: int) -> None:
        for _ in range(times):
            self.client.get("/users/me", name="GET /users/me")

    def post_composition(self, gif_url: str, acknowledge_frame_reduction: bool):
        with TARGET_IMAGE.open("rb") as target_file:
            return self.client.post(
                "/compositions",
                name="POST /compositions",
                data={
                    "gif_url": gif_url,
                    "acknowledge_frame_reduction": str(acknowledge_frame_reduction).lower(),
                },
                files={"target_file": (TARGET_IMAGE.name, target_file, "image/jpeg")},
            )

    def wait_for_sse_status(self, job_id: str, expected_status: str) -> None:
        started_at = time.monotonic()
        wait_metric_exception = None
        try:
            with self.client.get(
                f"/compositions/{job_id}/status",
                name="GET /compositions/{composition_job_id}/status",
                stream=True,
                timeout=STATUS_TIMEOUT_SECONDS + 5,
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    message = f"unexpected SSE status {response.status_code}"
                    wait_metric_exception = RuntimeError(message)
                    response.failure(message)
                    return

                for line in response.iter_lines(decode_unicode=True):
                    if time.monotonic() - started_at > STATUS_TIMEOUT_SECONDS:
                        message = f"SSE timed out after {STATUS_TIMEOUT_SECONDS}s"
                        wait_metric_exception = TimeoutError(message)
                        response.failure(message)
                        response.close()
                        return

                    if not line or not line.startswith("data: "):
                        continue

                    try:
                        event = json.loads(line.removeprefix("data: "))
                    except JSONDecodeError as exc:
                        wait_metric_exception = exc
                        response.failure(f"invalid SSE event JSON: {exc}")
                        return

                    if "error" in event:
                        wait_metric_exception = RuntimeError(event["error"])
                        response.failure(event["error"])
                        return

                    status = event["status"]
                    if status in ("COMPLETED", "FAILED"):
                        if status != expected_status:
                            message = f"expected {expected_status}, got {status}"
                            wait_metric_exception = RuntimeError(message)
                            response.failure(message)
                        else:
                            response.success()
                        response.close()
                        return

                wait_metric_exception = RuntimeError("SSE closed before terminal status")
                response.failure("SSE closed before terminal status")
        except Exception as exc:
            wait_metric_exception = exc
            raise
        finally:
            self.environment.events.request.fire(
                request_type="SSE",
                name="WAIT /compositions/{composition_job_id}/terminal_status",
                response_time=(time.monotonic() - started_at) * 1000,
                response_length=0,
                exception=wait_metric_exception,
            )
