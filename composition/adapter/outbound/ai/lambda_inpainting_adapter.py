import json

import aioboto3

from composition.application.ports.outbound.ai.image_inpainting_port import (
    ImageInpaintingPort,
    DraftGenerationCommand,
    FramesCompositingCommand,
)

FUNCTION_NAME = "gifgloo-ai-processor"


class LambdaInpaintingAdapter(ImageInpaintingPort):
    def __init__(self, region: str = "ap-northeast-2"):
        self._region = region

    async def _invoke(self, payload: dict) -> dict:
        session = aioboto3.Session()
        async with session.client("lambda", region_name=self._region) as client:
            response = await client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
            result = json.loads(await response["Payload"].read())

        if "errorMessage" in result:
            raise RuntimeError(f"Lambda 오류: {result['errorMessage']}")
        return result

    async def generate_draft(self, command: DraftGenerationCommand) -> str:
        await self._invoke({
            "action": "generate_draft",
            "target_key": command.target_key,
            "ref_frame_key": command.ref_frame_key,
            "spec": {
                "object_draft": command.spec.object_draft,
                "draft_reference_frame": command.spec.draft_reference_frame,
                "preserve": command.spec.preserve,
                "frame_directions": command.spec.frame_directions,
            },
            "draft_key": command.draft_key,
        })
        return command.draft_key

    async def composite_frames(self, command: FramesCompositingCommand) -> list[str]:
        result = await self._invoke({
            "action": "composite_frames",
            "job_id": command.job_id,
            "frame_keys": command.frame_keys,
            "draft_key": command.draft_key,
            "spec": {
                "object_draft": command.spec.object_draft,
                "draft_reference_frame": command.spec.draft_reference_frame,
                "preserve": command.spec.preserve,
                "frame_directions": command.spec.frame_directions,
            },
        })
        return result["composited_keys"]
