from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GifFrame:
    index: int
    r2_key: str
    duration_ms: int


@dataclass
class GifProcessingResult:
    frames: list[GifFrame]

    @property
    def frame_keys(self) -> list[str]:
        return [f.r2_key for f in self.frames]

    @property
    def durations_ms(self) -> list[int]:
        return [f.duration_ms for f in self.frames]


class GifProcessingPort(ABC):
    @abstractmethod
    async def extract_frames(self, gif_url: str, max_frames: int, job_id: str) -> GifProcessingResult:
        """프레임을 R2 temp에 저장하고 frame key 목록과 duration 반환"""
        pass

    @abstractmethod
    async def build_gif(self, frames_r2_keys: list[str], durations_ms: list[int], output_key: str) -> None:
        """frames_r2_keys에서 프레임 읽어 GIF 만들고 output_key에 R2 직접 저장"""
        pass
