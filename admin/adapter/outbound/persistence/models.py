from sqlalchemy import Column, DateTime, Index, JSON, String

from config.database import Base


class AdminAuditLogModel(Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("uq_admin_audit_logs_idempotency_key", "idempotency_key", unique=True),
    )

    id = Column(String, primary_key=True)
    admin_user_id = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    metadata_json = Column(JSON, nullable=False)
    idempotency_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
