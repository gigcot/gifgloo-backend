from abc import ABC, abstractmethod
from dataclasses import dataclass

from composition.application.ports.outbound.ai.composition_analysis_port import CompositionSpec


@dataclass
class DraftGenerationCommand:
    target: bytes                  # 타겟 이미지 PNG bytes
    spec: CompositionSpec
    frames: list[bytes] | None = None  # mix 타입일 때만 — draft_reference_frame 참조용


@dataclass
class FrameCompositingCommand:
    frame: bytes          # 베이스 GIF 프레임 PNG bytes
    draft: bytes          # STEP 2에서 생성된 초안 PNG bytes
    spec: CompositionSpec
    frame_idx: int


class ImageInpaintingPort(ABC):
    @abstractmethod
    async def generate_draft(self, command: DraftGenerationCommand) -> bytes:
        pass

    @abstractmethod
    async def composite_frame(self, command: FrameCompositingCommand) -> bytes:
        pass
