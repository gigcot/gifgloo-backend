from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AiCompositionRequest:
    base_url: str
    overlay_url: str


@dataclass
class AiCompositionResult:
    result_url: str


class AiModelPort(ABC):
    @abstractmethod
    def compose(self, request: AiCompositionRequest) -> AiCompositionResult:
        pass
