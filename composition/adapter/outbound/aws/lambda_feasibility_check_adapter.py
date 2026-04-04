import json

import aioboto3

from composition.application.ports.outbound.aws.feasibility_check_port import (
    FeasibilityCheckPort,
    FeasibilityCheckCommand,
    FeasibilityCheckResult,
)

FUNCTION_NAME = "gifgloo-gif-processor"


class LambdaFeasibilityCheckAdapter(FeasibilityCheckPort):
    def __init__(self, region: str = "ap-northeast-2"):
        self._region = region

    async def check(self, command: FeasibilityCheckCommand) -> FeasibilityCheckResult:
        session = aioboto3.Session()
        async with session.client("lambda", region_name=self._region) as client:
            response = await client.invoke(
                FunctionName=FUNCTION_NAME,
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "action": "check_feasibility",
                    "gif_url": command.gif_url,
                }),
            )
            result = json.loads(await response["Payload"].read())

        if "errorMessage" in result:
            raise RuntimeError(f"Lambda 오류: {result['errorMessage']}")

        return FeasibilityCheckResult(
            ok=result["ok"],
            frame_count=result["frame_count"],
            reason=result["reason"],
        )
