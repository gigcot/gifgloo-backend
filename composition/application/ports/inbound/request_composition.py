from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RequestCompositionCommand:
    user_id: str
    base_asset_id: str
    overlay_asset_id: str


@dataclass
class RequestCompositionResult:
    composition_job_id: str


class RequestCompositionPort(ABC):
    @abstractmethod
    def execute(self, command: RequestCompositionCommand) -> RequestCompositionResult:
        pass
