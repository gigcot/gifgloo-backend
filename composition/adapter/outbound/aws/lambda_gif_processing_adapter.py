import base64
import json

import boto3

from composition.application.ports.outbound.aws.gif_processing_port import (
    GifProcessingPort,
    GifFrame,
    GifProcessingResult,
)

FUNCTION_NAME = "gifgloo-gif-processor"


class LambdaGifProcessingAdapter(GifProcessingPort):
    def __init__(self, region: str = "ap-northeast-2"):
        self._client = boto3.client("lambda", region_name=region)

    def _invoke(self, payload: dict) -> dict:
        response = self._client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
        result = json.loads(response["Payload"].read())

        if "errorMessage" in result:
            raise RuntimeError(f"Lambda 오류: {result['errorMessage']}")

        return result

    def count_frames(self, gif_bytes: bytes) -> int:
        result = self._invoke({
            "action": "count_frames",
            "gif_b64": base64.b64encode(gif_bytes).decode(),
        })
        return result["count"]

    def extract_frames(self, gif_bytes: bytes) -> GifProcessingResult:
        result = self._invoke({
            "action": "extract_frames",
            "gif_b64": base64.b64encode(gif_bytes).decode(),
        })

        frames = [
            GifFrame(
                index=i,
                png_bytes=base64.b64decode(f_b64),
                duration_ms=result["durations_ms"][i],
            )
            for i, f_b64 in enumerate(result["frames"])
        ]
        return GifProcessingResult(frames=frames)

    def build_gif(self, frames_png: list[bytes], durations_ms: list[int]) -> bytes:
        result = self._invoke({
            "action": "build_gif",
            "frames_b64": [base64.b64encode(f).decode() for f in frames_png],
            "durations_ms": durations_ms,
        })
        return base64.b64decode(result["gif_b64"])
