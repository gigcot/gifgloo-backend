from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImageCompositionRequest:
    base_url: str
    overlay_url: str


@dataclass
class ImageCompositionResult:
    result_url: str


class ImageCompositionPort(ABC):
    @abstractmethod
    def compose(self, request: ImageCompositionRequest) -> ImageCompositionResult:
        pass
