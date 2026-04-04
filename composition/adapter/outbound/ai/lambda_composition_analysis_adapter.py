import json

import aioboto3

from composition.application.ports.outbound.ai.composition_analysis_port import (
    CompositionAnalysisPort,
    CompositionAnalysisCommand,
    CompositionSpec,
)

FUNCTION_NAME = "gifgloo-ai-processor"


class LambdaCompositionAnalysisAdapter(CompositionAnalysisPort):
    def __init__(self, region: str = "ap-northeast-2"):
        self._region = region

    async def analyze(self, command: CompositionAnalysisCommand) -> CompositionSpec:
        session = aioboto3.Session()
        async with session.client("lambda", region_name=self._region) as client:
            response = await client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "action": "analyze",
                    "frame_keys": command.frame_keys,
                    "target_key": command.target_key,
                }),
            )
            result = json.loads(await response["Payload"].read())

        if "errorMessage" in result:
            raise RuntimeError(f"Lambda 오류: {result['errorMessage']}")

        return CompositionSpec(
            object_draft=result["object_draft"],
            draft_reference_frame=result["draft_reference_frame"],
            preserve=result["preserve"],
            frame_directions=result["frame_directions"],
        )
