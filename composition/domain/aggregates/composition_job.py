from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from composition.domain.entities.composition_frame import CompositionFrame
from composition.domain.value_objects.composition_image import CompositionImage
from composition.domain.value_objects.composition_status import CompositionStatus
from composition.domain.value_objects.composition_type import CompositionType, CompositionTypeValue


class CompositionJob:
    def __init__(
        self,
        user_id: str,
        base_image: CompositionImage,
        overlay_image: CompositionImage,
    ):
        self.id: str = str(uuid.uuid4())
        self.user_id: str = user_id
        self.base_image: CompositionImage = base_image
        self.overlay_image: CompositionImage = overlay_image
        self.type: CompositionType = CompositionType.from_images(base_image, overlay_image)
        self.status: CompositionStatus = CompositionStatus.PENDING
        self.frames: list[CompositionFrame] = []
        self.result_asset_id: Optional[str] = None
        self.failed_reason: Optional[str] = None
        self.created_at: datetime = datetime.now(timezone.utc)

    # ── 상태 전이 ──

    def start_processing(self) -> None:
        if self.status != CompositionStatus.PENDING:
            raise ValueError("대기 중인 작업만 처리 시작할 수 있습니다")
        self.status = CompositionStatus.PROCESSING

    def complete(self, result_asset_id: str) -> None:
        if self.type.value != CompositionTypeValue.STATIC_STATIC:
            raise ValueError("정적 합성만 직접 완료할 수 있습니다")
        if self.status != CompositionStatus.PROCESSING:
            raise ValueError("처리 중인 작업만 완료할 수 있습니다")
        self.status = CompositionStatus.COMPLETED
        self.result_asset_id = result_asset_id

    def fail(self, reason: str) -> None:
        self.status = CompositionStatus.FAILED
        self.failed_reason = reason

    # ── 프레임 관리 (GIF 전용) ──

    def init_frames(self, frame_count: int) -> None:
        if self.type.value != CompositionTypeValue.GIF_STATIC:
            raise ValueError("GIF 합성 작업에서만 프레임을 초기화할 수 있습니다")
        self.frames = [CompositionFrame(i) for i in range(frame_count)]

    def complete_frame(self, frame_id: str, result_asset_id: str) -> None:
        frame = self._find_frame(frame_id)
        frame.complete(result_asset_id)
        if all(f.status == CompositionStatus.COMPLETED for f in self.frames):
            self.status = CompositionStatus.COMPLETED

    def fail_frame(self, frame_id: str, reason: str) -> None:
        frame = self._find_frame(frame_id)
        frame.fail(reason)
        self.fail(reason)

    def _find_frame(self, frame_id: str) -> CompositionFrame:
        for frame in self.frames:
            if frame.id == frame_id:
                return frame
        raise ValueError(f"프레임을 찾을 수 없습니다: {frame_id}")
