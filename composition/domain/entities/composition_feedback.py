from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CompositionFeedback:
    composition_job_id: str
    satisfied: bool
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
