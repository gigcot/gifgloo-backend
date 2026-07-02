import asyncio
import os

import httpx

from composition.application.ports.outbound.aws.pipeline_trigger_port import (
    PipelineTriggerCommand,
    PipelineTriggerPort,
)
from composition.domain.value_objects.composition_stage import CompositionStage
from shared.metrics import FAKE_PIPELINE_TRIGGER_TOTAL


class FakePipelineTriggerAdapter(PipelineTriggerPort):
    def __init__(self):
        self._callback_url = os.environ["LOADTEST_CALLBACK_URL"].rstrip("/")
        self._internal_secret = os.environ["INTERNAL_SECRET"]
        self._mode = os.environ["LOADTEST_PIPELINE_MODE"].lower()
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
        FAKE_PIPELINE_TRIGGER_TOTAL.labels(mode=self._mode).inc()
        asyncio.create_task(self._run_pipeline(command))

    async def _run_pipeline(self, command: PipelineTriggerCommand) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            await self._checkpoint(client, command.job_id, CompositionStage.EXTRACTING_FRAMES)
            await self._checkpoint(
                client,
                command.job_id,
                CompositionStage.ANALYZING,
                {"durations_ms": command.durations_ms},
            )
            await self._checkpoint(
                client,
                command.job_id,
                CompositionStage.GENERATING_DRAFT,
                {"spec": command.spec or {"mode": "loadtest"}},
            )
            await self._checkpoint(client, command.job_id, CompositionStage.COMPOSITING)
            await self._checkpoint(client, command.job_id, CompositionStage.BUILDING_GIF)
            await asyncio.sleep(self._completion_delay_seconds)

            if self._mode == "fail":
                await self._post(
                    client,
                    f"/internal/compositions/{command.job_id}/fail",
                    {"reason": "loadtest pipeline failure"},
                )
                return

            await self._post(
                client,
                f"/internal/compositions/{command.job_id}/complete",
                {
                    "draft_key": f"compositions/{command.job_id}/draft.png",
                    "result_key": f"compositions/{command.job_id}/result.gif",
                },
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
