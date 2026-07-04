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

TOKEN_CSV = Path(os.environ["LOADTEST_TOKEN_OUTPUT_PATH"])
TARGET_IMAGE = Path(os.environ["LOADTEST_TARGET_IMAGE_PATH"])
GIF_URL = os.environ["LOADTEST_GIF_URL"]
PIPELINE_FAIL_MARKER = os.environ["LOADTEST_PIPELINE_FAIL_MARKER"]
HOME_PAGE_WEIGHT = int(os.environ["LOADTEST_HOME_PAGE_WEIGHT"])
COMPOSE_PAGE_WEIGHT = int(os.environ["LOADTEST_COMPOSE_PAGE_WEIGHT"])
SUCCESS_WEIGHT = int(os.environ["LOADTEST_SUCCESS_WEIGHT"])
FAIL_WEIGHT = int(os.environ["LOADTEST_FAIL_WEIGHT"])
MY_ASSETS_PAGE_WEIGHT = int(os.environ["LOADTEST_MY_ASSETS_PAGE_WEIGHT"])
STATUS_TIMEOUT_SECONDS = float(os.environ["LOADTEST_STATUS_TIMEOUT_SECONDS"])


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

    @task(HOME_PAGE_WEIGHT)
    def home_page_load(self) -> None:
        self.client.get("/users/me", name="GET /users/me")
        self.client.get("/credits/balance", name="GET /credits/balance")
        self.client.get("/compositions", name="GET /compositions")

    @task(COMPOSE_PAGE_WEIGHT)
    def compose_page_load(self) -> None:
        self.client.get("/users/me", name="GET /users/me")
        self.client.get("/credits/balance", name="GET /credits/balance")

    @task(SUCCESS_WEIGHT)
    def composition_success_flow(self) -> None:
        self.composition_flow(should_fail=False)

    @task(FAIL_WEIGHT)
    def composition_fail_flow(self) -> None:
        self.composition_flow(should_fail=True)

    @task(MY_ASSETS_PAGE_WEIGHT)
    def my_assets_page_load(self) -> None:
        self.client.get("/compositions", name="GET /compositions")

    def composition_flow(self, should_fail: bool) -> None:
        self.compose_page_load()

        gif_url = self.fail_gif_url() if should_fail else GIF_URL

        with TARGET_IMAGE.open("rb") as target_file:
            response = self.client.post(
                "/compositions",
                name="POST /compositions",
                data={
                    "gif_url": gif_url,
                    "acknowledge_frame_reduction": "true",
                },
                files={"target_file": (TARGET_IMAGE.name, target_file, "image/jpeg")},
            )
        if response.status_code != 200:
            return

        job_id = response.json()["composition_job_id"]
        expected_status = "FAILED" if should_fail else "COMPLETED"
        self.wait_for_sse_status(job_id, expected_status)
        self.client.get("/compositions", name="GET /compositions")

    def fail_gif_url(self) -> str:
        separator = "&" if "?" in GIF_URL else "?"
        return f"{GIF_URL}{separator}loadtest={PIPELINE_FAIL_MARKER}"

    def wait_for_sse_status(self, job_id: str, expected_status: str) -> None:
        started_at = time.monotonic()
        with self.client.get(
            f"/compositions/{job_id}/status",
            name="GET /compositions/{composition_job_id}/status",
            stream=True,
            timeout=STATUS_TIMEOUT_SECONDS + 5,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected SSE status {response.status_code}")
                return

            for line in response.iter_lines(decode_unicode=True):
                if time.monotonic() - started_at > STATUS_TIMEOUT_SECONDS:
                    response.failure(f"SSE timed out after {STATUS_TIMEOUT_SECONDS}s")
                    response.close()
                    return

                if not line or not line.startswith("data: "):
                    continue

                try:
                    event = json.loads(line.removeprefix("data: "))
                except JSONDecodeError as exc:
                    response.failure(f"invalid SSE event JSON: {exc}")
                    return

                if "error" in event:
                    response.failure(event["error"])
                    return

                status = event["status"]
                if status in ("COMPLETED", "FAILED"):
                    if status != expected_status:
                        response.failure(f"expected {expected_status}, got {status}")
                    return

            response.failure("SSE closed before terminal status")
