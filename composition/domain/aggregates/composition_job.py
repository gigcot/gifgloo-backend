from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from composition.domain.value_objects.composition_status import CompositionStatus


class CompositionJob:
    def __init__(self, user_id: str):
        self.id: str = str(uuid.uuid4())
        self.user_id: str = user_id
        self.status: CompositionStatus = CompositionStatus.PENDING
        self.source_gif_asset_id: Optional[str] = None
        self.target_asset_id: Optional[str] = None
        self.draft_asset_id: Optional[str] = None
        self.result_asset_id: Optional[str] = None
        self.result_url: Optional[str] = None
        self.failed_reason: Optional[str] = None
        self.created_at: datetime = datetime.now(timezone.utc)

    def start_processing(self) -> None:
        if self.status != CompositionStatus.PENDING:
            raise ValueError("대기 중인 작업만 처리 시작할 수 있습니다")
        self.status = CompositionStatus.PROCESSING

    def complete(self, result_url: str) -> None:
        if self.status != CompositionStatus.PROCESSING:
            raise ValueError("처리 중인 작업만 완료할 수 있습니다")
        self.status = CompositionStatus.COMPLETED
        self.result_url = result_url

    def fail(self, reason: str) -> None:
        self.status = CompositionStatus.FAILED
        self.failed_reason = reason

