from abc import ABC, abstractmethod
from dataclasses import dataclass

from composition.application.ports.outbound.ai.composition_analysis_port import CompositionSpec


@dataclass
class DraftGenerationCommand:
    target_key: str                # R2 타겟 이미지 key
    spec: CompositionSpec
    draft_key: str                 # 저장할 R2 key (서비스가 make_key로 생성해서 전달)
    ref_frame_key: str | None = None  # mix 타입일 때만 — draft_reference_frame 참조용


@dataclass
class FramesCompositingCommand:
    job_id: str
    frame_keys: list[str]   # R2 베이스 프레임 key 목록 (전체)
    draft_key: str          # R2 드래프트 key
    spec: CompositionSpec


class ImageInpaintingPort(ABC):
    @abstractmethod
    async def generate_draft(self, command: DraftGenerationCommand) -> str:
        """드래프트를 생성해 draft_key에 R2 저장, draft_key 반환"""
        pass

    @abstractmethod
    async def composite_frames(self, command: FramesCompositingCommand) -> list[str]:
        """Lambda 내부에서 병렬 합성, composited frame R2 key 목록 반환"""
        pass
