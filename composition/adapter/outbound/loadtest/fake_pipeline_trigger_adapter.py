import asyncio
import logging
import os

import httpx

from composition.application.ports.outbound.aws.pipeline_trigger_port import (
    PipelineTriggerCommand,
    PipelineTriggerPort,
)
from composition.domain.value_objects.composition_stage import CompositionStage
from shared.metrics import FAKE_PIPELINE_TRIGGER_TOTAL


class FakePipelineTriggerAdapter(PipelineTriggerPort):
    def __init__(self, client: httpx.AsyncClient):
        self._client = client
        self._tasks: set[asyncio.Task[None]] = set()
        self._accepted_job_ids: set[str] = set()
        self._callback_url = os.environ["LOADTEST_CALLBACK_URL"].rstrip("/")
        self._internal_secret = os.environ["INTERNAL_SECRET"]
        self._fail_marker = os.environ["LOADTEST_PIPELINE_FAIL_MARKER"]
        self._fail_stage = (
            CompositionStage(os.environ["LOADTEST_PIPELINE_FAIL_STAGE"])
            if "LOADTEST_PIPELINE_FAIL_STAGE" in os.environ
            else None
        )
        self._stage_delay_seconds = {
            CompositionStage.EXTRACTING_FRAMES: float(
                os.environ["LOADTEST_DELAY_EXTRACTING_FRAMES_SECONDS"]
            ),
            CompositionStage.ANALYZING: float(os.environ["LOADTEST_DELAY_ANALYZING_SECONDS"]),
            CompositionStage.GENERATING_DRAFT: float(
                os.environ["LOADTEST_DELAY_GENERATING_DRAFT_SECONDS"]
            ),
            CompositionStage.COMPOSITING: float(os.environ["LOADTEST_DELAY_COMPOSITING_SECONDS"]),
            CompositionStage.BUILDING_GIF: float(os.environ["LOADTEST_DELAY_BUILDING_GIF_SECONDS"]),
        }
        self._completion_delay_seconds = float(os.environ["LOADTEST_DELAY_COMPLETION_SECONDS"])

    async def trigger(self, command: PipelineTriggerCommand) -> None:
        if command.job_id in self._accepted_job_ids:
            return
        self._accepted_job_ids.add(command.job_id)
        mode = self._mode_for(command)
        FAKE_PIPELINE_TRIGGER_TOTAL.labels(mode=mode).inc()
        task = asyncio.create_task(self._run_pipeline(command))
        self._tasks.add(task)
        task.add_done_callback(self._pipeline_finished)

    async def aclose(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _pipeline_finished(self, task: asyncio.Task[None]) -> None:
        self._tasks.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if error:
            logging.getLogger(__name__).error(
                "fake pipeline callback failed",
                exc_info=error,
            )

    async def _run_pipeline(self, command: PipelineTriggerCommand) -> None:
        mode = self._mode_for(command)
        await self._checkpoint_or_fail(self._client, command, CompositionStage.EXTRACTING_FRAMES)
        if mode == "fail" and self._fail_stage == CompositionStage.EXTRACTING_FRAMES:
            return

        await self._checkpoint_or_fail(
            self._client,
            command,
            CompositionStage.ANALYZING,
            {"durations_ms": command.durations_ms},
        )
        if mode == "fail" and self._fail_stage == CompositionStage.ANALYZING:
            return

        await self._checkpoint_or_fail(
            self._client,
            command,
            CompositionStage.GENERATING_DRAFT,
            {"spec": command.spec or {"mode": "loadtest"}},
        )
        if mode == "fail" and self._fail_stage == CompositionStage.GENERATING_DRAFT:
            return

        await self._checkpoint_or_fail(self._client, command, CompositionStage.COMPOSITING)
        if mode == "fail" and self._fail_stage == CompositionStage.COMPOSITING:
            return

        await self._checkpoint_or_fail(self._client, command, CompositionStage.BUILDING_GIF)
        if mode == "fail" and self._fail_stage == CompositionStage.BUILDING_GIF:
            return

        await asyncio.sleep(self._completion_delay_seconds)

        if mode == "fail":
            await self._post(
                self._client,
                f"/internal/compositions/{command.job_id}/fail",
                {"reason": "loadtest pipeline failure"},
            )
            return

        await self._post(
            self._client,
            f"/internal/compositions/{command.job_id}/complete",
            {
                "draft_key": f"compositions/{command.job_id}/draft.png",
                "result_key": f"compositions/{command.job_id}/result.gif",
            },
        )

    def _mode_for(self, command: PipelineTriggerCommand) -> str:
        if self._fail_marker in command.gif_url:
            return "fail"
        return "complete"

    async def _checkpoint_or_fail(
        self,
        client: httpx.AsyncClient,
        command: PipelineTriggerCommand,
        stage: CompositionStage,
        extra: dict | None = None,
    ) -> None:
        await self._checkpoint(client, command.job_id, stage, extra)
        if self._mode_for(command) == "fail" and self._fail_stage == stage:
            await self._post(
                client,
                f"/internal/compositions/{command.job_id}/fail",
                {"reason": f"loadtest pipeline failure at {stage.value}"},
            )

    async def _checkpoint(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        stage: CompositionStage,
        extra: dict | None = None,
    ) -> None:
        body = {"stage": stage.value}
        if extra:
            body.update(extra)
        await self._post(client, f"/internal/compositions/{job_id}/checkpoint", body)
        await asyncio.sleep(self._stage_delay_seconds[stage])

    async def _post(self, client: httpx.AsyncClient, path: str, body: dict) -> None:
        response = await client.post(
            f"{self._callback_url}{path}",
            json=body,
            headers={"X-Internal-Secret": self._internal_secret},
        )
        response.raise_for_status()
