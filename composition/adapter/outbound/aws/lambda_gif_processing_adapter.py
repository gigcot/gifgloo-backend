import json

import aioboto3

from composition.application.ports.outbound.aws.gif_processing_port import (
    GifProcessingPort,
    GifFrame,
    GifProcessingResult,
)

FUNCTION_NAME = "gifgloo-gif-processor"


class LambdaGifProcessingAdapter(GifProcessingPort):
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

    async def extract_frames(self, gif_url: str, max_frames: int, job_id: str) -> GifProcessingResult:
        result = await self._invoke({
            "action": "extract_frames",
            "gif_url": gif_url,
            "max_frames": max_frames,
            "job_id": job_id,
        })
        frames = [
            GifFrame(
                index=i,
                r2_key=key,
                duration_ms=result["durations_ms"][i],
            )
            for i, key in enumerate(result["frame_keys"])
        ]
        return GifProcessingResult(frames=frames)

    async def build_gif(self, frames_r2_keys: list[str], durations_ms: list[int], output_key: str) -> None:
        await self._invoke({
            "action": "build_gif",
            "frames_r2_keys": frames_r2_keys,
            "durations_ms": durations_ms,
            "output_key": output_key,
        })
