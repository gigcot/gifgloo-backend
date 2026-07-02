import os

from composition.application.ports.outbound.aws.feasibility_check_port import (
    FeasibilityCheckCommand,
    FeasibilityCheckPort,
    FeasibilityCheckResult,
)
class FakeFeasibilityCheckAdapter(FeasibilityCheckPort):
    def __init__(self):
        self._blocked_marker = os.environ["LOADTEST_FEASIBILITY_BLOCK_MARKER"]
        self._frame_count = int(os.environ["LOADTEST_FEASIBILITY_FRAME_COUNT"])

    async def check(self, command: FeasibilityCheckCommand) -> FeasibilityCheckResult:
        if self._blocked_marker in command.gif_url:
            return FeasibilityCheckResult(
                ok=False,
                frame_count=0,
                reason="loadtest feasibility rejected",
            )

        return FeasibilityCheckResult(
            ok=True,
            frame_count=self._frame_count,
            reason=None,
        )
