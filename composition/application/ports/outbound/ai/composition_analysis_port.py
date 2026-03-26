from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompositionSpec:
    object_draft: dict        # object_match, type, note
    draft_reference_frame: int | None
    preserve: str
    frame_directions: list[dict]  # [{frame_idx, description}, ...]


@dataclass
class CompositionAnalysisCommand:
    frames: list[bytes]   # GIF 프레임 PNG bytes 목록
    target: bytes         # 타겟 이미지 PNG bytes


class CompositionAnalysisPort(ABC):
    @abstractmethod
    async def analyze(self, command: CompositionAnalysisCommand) -> CompositionSpec:
        pass
