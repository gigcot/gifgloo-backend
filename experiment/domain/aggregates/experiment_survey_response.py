from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class ExperimentSurveyResponse:
    experiment_code: str
    user_id: str
    answers: dict[str, object]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
