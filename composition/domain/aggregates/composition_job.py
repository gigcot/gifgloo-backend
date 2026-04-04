from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import InvalidStateException


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
            raise InvalidStateException("대기 중인 작업만 처리 시작할 수 있습니다")
        self.status = CompositionStatus.PROCESSING

    def complete(
        self,
        result_url: str,
        source_gif_asset_id: str,
        target_asset_id: str,
        draft_asset_id: str,
        result_asset_id: str,
    ) -> None:
        if self.status != CompositionStatus.PROCESSING:
            raise InvalidStateException("처리 중인 작업만 완료할 수 있습니다")
        self.status = CompositionStatus.COMPLETED
        self.result_url = result_url
        self.source_gif_asset_id = source_gif_asset_id
        self.target_asset_id = target_asset_id
        self.draft_asset_id = draft_asset_id
        self.result_asset_id = result_asset_id

    def fail(self, reason: str) -> None:
        self.status = CompositionStatus.FAILED
        self.failed_reason = reason

