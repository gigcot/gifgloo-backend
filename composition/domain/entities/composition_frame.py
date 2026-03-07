from typing import Optional
import uuid
from composition.domain.value_objects.composition_status import CompositionStatus



class CompositionFrame:
    def __init__(self, frame_index: int):
        self.id: str = str(uuid.uuid4())
        self.frame_index: int = frame_index
        self.status: CompositionStatus = CompositionStatus.PENDING
        self.result_asset_id: Optional[str] = None
        self.failed_reason: Optional[str] = None

    def complete(self, result_asset_id: str) -> None:
        self.status = CompositionStatus.COMPLETED
        self.result_asset_id = result_asset_id

    def fail(self, reason: str) -> None:
        self.status = CompositionStatus.FAILED
        self.failed_reason = reason
