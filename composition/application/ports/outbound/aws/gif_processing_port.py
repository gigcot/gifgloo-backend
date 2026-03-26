from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GifFrame:
    index: int
    png_bytes: bytes
    duration_ms: int


@dataclass
class GifProcessingResult:
    frames: list[GifFrame]


class GifProcessingPort(ABC):
    @abstractmethod
    def count_frames(self, gif_bytes: bytes) -> int:
        pass

    @abstractmethod
    def extract_frames(self, gif_bytes: bytes) -> GifProcessingResult:
        pass

    @abstractmethod
    def build_gif(self, frames_png: list[bytes], durations_ms: list[int]) -> bytes:
        pass
