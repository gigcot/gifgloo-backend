from datetime import datetime, timezone
import uuid


class Audit:
    def __init__(
            self,
            service_type,
            action_type,
            user_id,
    ):
        self.id = str(uuid.uuid4())
        self.user_id = user_id
        self.service_type = service_type
        self.action_type = action_type
        self.created_at = datetime.now(timezone.utc)

