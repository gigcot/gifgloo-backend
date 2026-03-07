
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeleteAssetCommand:
    user_id: str
    asset_id: str

class DeleteAssetPort(ABC):
    @abstractmethod
    def execute(self, command: DeleteAssetCommand) -> None:
        pass