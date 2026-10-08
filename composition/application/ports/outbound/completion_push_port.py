from dataclasses import dataclass
from typing import Protocol, Literal


@dataclass(frozen=True)
class CompletionPushCommand:
    endpoint: str
    p256dh: str
    auth: str
    job_id: str


class CompletionPushPort(Protocol):
    async def send(self, command: CompletionPushCommand) -> Literal["accepted", "retry", "invalid"]: ...
