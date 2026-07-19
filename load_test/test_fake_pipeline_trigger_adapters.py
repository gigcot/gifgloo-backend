import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from composition.adapter.outbound.loadtest.fake_pipeline_trigger_adapter import (
    FakePipelineTriggerAdapter,
)
from composition.adapter.outbound.loadtest.fake_pipeline_worker_trigger_adapter import (
    FakePipelineWorkerTriggerAdapter,
)
from composition.application.ports.outbound.aws.pipeline_trigger_port import (
    PipelineTriggerCommand,
)


def _command() -> PipelineTriggerCommand:
    return PipelineTriggerCommand(
        job_id="job-1",
        gif_url="https://gif.example/source.gif",
        target_key="target/job-1.png",
        user_id="user-1",
    )


class _RetryingHttpClient:
    def __init__(self, failures: int):
        self.failures = failures
        self.calls = 0

    async def post(self, url, **kwargs) -> httpx.Response:
        self.calls += 1
        request = httpx.Request("POST", url)
        if self.calls <= self.failures:
            raise httpx.ReadError("connection closed", request=request)
        return httpx.Response(202, request=request)


class FakePipelineTriggerAdapterTest(unittest.IsolatedAsyncioTestCase):
    async def test_accepts_each_job_only_once(self):
        env = {
            "LOADTEST_CALLBACK_URL": "http://127.0.0.1:8001",
            "INTERNAL_SECRET": "secret",
            "LOADTEST_PIPELINE_FAIL_MARKER": "__FAIL__",
            "LOADTEST_DELAY_EXTRACTING_FRAMES_SECONDS": "0",
            "LOADTEST_DELAY_ANALYZING_SECONDS": "0",
            "LOADTEST_DELAY_GENERATING_DRAFT_SECONDS": "0",
            "LOADTEST_DELAY_COMPOSITING_SECONDS": "0",
            "LOADTEST_DELAY_BUILDING_GIF_SECONDS": "0",
            "LOADTEST_DELAY_COMPLETION_SECONDS": "0",
        }
        with patch.dict("os.environ", env):
            adapter = FakePipelineTriggerAdapter(AsyncMock())
        adapter._run_pipeline = AsyncMock()

        await adapter.trigger(_command())
        await adapter.trigger(_command())
        await asyncio.sleep(0)

        adapter._run_pipeline.assert_awaited_once()
        await adapter.aclose()


class FakePipelineWorkerTriggerAdapterTest(unittest.IsolatedAsyncioTestCase):
    def _adapter(self, client) -> FakePipelineWorkerTriggerAdapter:
        with patch.dict(
            "os.environ",
            {
                "LOADTEST_PIPELINE_WORKER_URL": "http://127.0.0.1:8012",
                "INTERNAL_SECRET": "secret",
                "LOADTEST_PIPELINE_FAIL_MARKER": "__FAIL__",
            },
        ):
            return FakePipelineWorkerTriggerAdapter(client)

    async def test_retries_one_transport_error(self):
        client = _RetryingHttpClient(failures=1)

        await self._adapter(client).trigger(_command())

        self.assertEqual(client.calls, 2)

    async def test_raises_after_second_transport_error(self):
        client = _RetryingHttpClient(failures=2)

        with self.assertRaises(httpx.ReadError):
            await self._adapter(client).trigger(_command())

        self.assertEqual(client.calls, 2)
