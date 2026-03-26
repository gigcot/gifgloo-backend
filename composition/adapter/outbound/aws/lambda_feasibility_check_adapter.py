import base64
import json

import boto3

from composition.application.ports.outbound.aws.feasibility_check_port import (
    FeasibilityCheckPort,
    FeasibilityCheckCommand,
    FeasibilityCheckResult,
)

FUNCTION_NAME = "gifgloo-gif-processor"


class LambdaFeasibilityCheckAdapter(FeasibilityCheckPort):
    def __init__(self, region: str = "ap-northeast-2"):
        self._client = boto3.client("lambda", region_name=region)

    def check(self, command: FeasibilityCheckCommand) -> FeasibilityCheckResult:
        payload = {
            "action": "check_feasibility",
            "gif_b64": base64.b64encode(command.gif_bytes).decode(),
            "target_b64": base64.b64encode(command.target_bytes).decode(),
        }
        response = self._client.invoke(
            FunctionName=FUNCTION_NAME,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
        result = json.loads(response["Payload"].read())

        if "errorMessage" in result:
            raise RuntimeError(f"Lambda 오류: {result['errorMessage']}")

        return FeasibilityCheckResult(ok=result["ok"], reason=result.get("reason"))
