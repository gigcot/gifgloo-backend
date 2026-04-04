import json

import aioboto3

from composition.application.ports.outbound.aws.pipeline_trigger_port import PipelineTriggerPort, PipelineTriggerCommand

FUNCTION_NAME = "gifgloo-ai-processor"


class LambdaPipelineTriggerAdapter(PipelineTriggerPort):
    def __init__(self, region: str = "ap-northeast-2"):
        self._region = region

    async def trigger(self, command: PipelineTriggerCommand) -> None:
        payload: dict = {
            "action": "run_pipeline",
            "job_id": command.job_id,
            "gif_url": command.gif_url,
            "user_id": command.user_id,
        }
        if command.resume_from:
            payload["resume_from"] = command.resume_from
        if command.durations_ms:
            payload["durations_ms"] = command.durations_ms
        if command.spec:
            payload["spec"] = command.spec

        session = aioboto3.Session()
        async with session.client("lambda", region_name=self._region) as client:
            await client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType="Event",
                Payload=json.dumps(payload),
            )
