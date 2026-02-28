from abc import ABC, abstractmethod
from dataclasses import dataclass

from composition.domain.value_objects.composition_image import ImageFormat


@dataclass
class AssetInfo:
    asset_id: str
    format: ImageFormat
    url: str


class AssetFetchPort(ABC):
    @abstractmethod
    def fetch(self, asset_id: str) -> AssetInfo:
        pass
