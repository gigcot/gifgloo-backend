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
    frame_keys: list[str]   # R2에 저장된 GIF 프레임 key 목록
    target_key: str         # R2에 저장된 타겟 이미지 key


class CompositionAnalysisPort(ABC):
    @abstractmethod
    async def analyze(self, command: CompositionAnalysisCommand) -> CompositionSpec:
        pass
