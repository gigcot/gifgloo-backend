from audit.application.ports.inbound.log_action import LogActionCommand, LogActionPort, LogActionResult
from audit.application.ports.outbound.persistence.audit_repository_port import AuditRepositoryPort


class LogActionService(LogActionPort):
    def __init__(
            self,
            log_rep: AuditRepositoryPort,
            # 모르겠노
    ):
        ...

    def execute(self) -> None:
        ...