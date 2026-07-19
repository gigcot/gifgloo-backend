import os
from dataclasses import asdict

import httpx

from composition.application.ports.outbound.aws.pipeline_trigger_port import (
    PipelineTriggerCommand,
    PipelineTriggerPort,
)
from shared.metrics import FAKE_PIPELINE_TRIGGER_TOTAL


class FakePipelineWorkerTriggerAdapter(PipelineTriggerPort):
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._worker_url = os.environ["LOADTEST_PIPELINE_WORKER_URL"].rstrip("/")
        self._internal_secret = os.environ["INTERNAL_SECRET"]
        self._fail_marker = os.environ["LOADTEST_PIPELINE_FAIL_MARKER"]

    async def trigger(self, command: PipelineTriggerCommand) -> None:
        mode = "fail" if self._fail_marker in command.gif_url else "complete"
        response = await self._client.post(
            f"{self._worker_url}/pipelines",
            json=asdict(command),
            headers={"X-Internal-Secret": self._internal_secret},
            timeout=5,
        )
        response.raise_for_status()
        FAKE_PIPELINE_TRIGGER_TOTAL.labels(mode=mode).inc()

    async def aclose(self) -> None:
        return
