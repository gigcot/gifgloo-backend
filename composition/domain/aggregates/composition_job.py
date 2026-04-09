from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from composition.domain.value_objects.composition_status import CompositionStatus
from composition.domain.value_objects.composition_stage import CompositionStage
from shared.exceptions import InvalidStateException


class CompositionJob:
    def __init__(self, user_id: str):
        self.id: str = str(uuid.uuid4())
        self.user_id: str = user_id
        self.status: CompositionStatus = CompositionStatus.PENDING
        self.stage: Optional[CompositionStage] = None
        self.gif_url: Optional[str] = None
        self.source_gif_url: Optional[str] = None
        self.target_url: Optional[str] = None
        self.source_gif_asset_id: Optional[str] = None
        self.target_asset_id: Optional[str] = None
        self.draft_asset_id: Optional[str] = None
        self.result_asset_id: Optional[str] = None
        self.result_url: Optional[str] = None
        self.failed_reason: Optional[str] = None
        self.durations_ms: Optional[list[int]] = None
        self.spec: Optional[dict] = None
        self.created_at: datetime = datetime.now(timezone.utc)

    def start_processing(self) -> None:
        if self.status != CompositionStatus.PENDING:
            raise InvalidStateException("대기 중인 작업만 처리 시작할 수 있습니다")
        self.status = CompositionStatus.PROCESSING

    def stage_extracting_frames(self) -> None:
        self.stage = CompositionStage.EXTRACTING_FRAMES

    def stage_analyzing(self, durations_ms: list[int]) -> None:
        self.stage = CompositionStage.ANALYZING
        self.durations_ms = durations_ms

    def stage_generating_draft(self, spec: dict) -> None:
        self.stage = CompositionStage.GENERATING_DRAFT
        self.spec = spec

    def stage_compositing(self) -> None:
        self.stage = CompositionStage.COMPOSITING

    def stage_building_gif(self) -> None:
        self.stage = CompositionStage.BUILDING_GIF

    def complete(self, result_url: str, draft_asset_id: str, result_asset_id: str) -> None:
        if self.status == CompositionStatus.COMPLETED:
            return
        if self.status != CompositionStatus.PROCESSING:
            raise InvalidStateException("처리 중인 작업만 완료할 수 있습니다")
        self.status = CompositionStatus.COMPLETED
        self.result_url = result_url
        self.draft_asset_id = draft_asset_id
        self.result_asset_id = result_asset_id

    def fail(self, reason: str) -> None:
        self.status = CompositionStatus.FAILED
        self.failed_reason = reason
