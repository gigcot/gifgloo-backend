from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from composition.domain.value_objects.composition_image import CompositionImage


class CompositionTypeValue(Enum):
    STATIC_STATIC = "STATIC_STATIC"
    GIF_STATIC    = "GIF_STATIC"


@dataclass(frozen=True)
class CompositionType:
    value: CompositionTypeValue

    @staticmethod
    def from_images(
        base: CompositionImage,
        overlay: CompositionImage,
    ) -> CompositionType:
        if overlay.is_gif():
            raise ValueError("오버레이 이미지는 정적이어야 합니다")
        if base.is_gif():
            return CompositionType(value=CompositionTypeValue.GIF_STATIC)
        return CompositionType(value=CompositionTypeValue.STATIC_STATIC)
