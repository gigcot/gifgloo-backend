from dataclasses import dataclass
from enum import Enum


class ImageRole(Enum):
    BASE    = "BASE"
    OVERLAY = "OVERLAY"


class ImageFormat(Enum):
    GIF  = "GIF"
    PNG  = "PNG"
    JPG  = "JPG"


@dataclass(frozen=True)
class CompositionImage:
    asset_id: str
    role: ImageRole
    format: ImageFormat

    def is_gif(self) -> bool:
        return self.format == ImageFormat.GIF
