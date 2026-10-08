from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, Index

from config.database import Base


class CompositionJobModel(Base):
    __tablename__ = "composition_jobs"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    gif_url = Column(String, nullable=True)
    source_gif_url = Column(String, nullable=True)
    target_url = Column(String, nullable=True)
    source_gif_asset_id = Column(String, nullable=True)
    target_asset_id = Column(String, nullable=True)
    draft_asset_id = Column(String, nullable=True)
    result_asset_id = Column(String, nullable=True)
    result_url = Column(String, nullable=True)
    failed_reason = Column(String, nullable=True)
    durations_ms = Column(JSON, nullable=True)
    spec = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class CompositionGateModel(Base):
    __tablename__ = "composition_gate"

    id = Column(Integer, primary_key=True)
    active_job_id = Column(String, nullable=True)
    active_run_id = Column(String, nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    last_edit_sent_at = Column(DateTime(timezone=True), nullable=True)


class CompositionFeedbackModel(Base):
    __tablename__ = "composition_feedbacks"

    composition_job_id = Column(
        String,
        ForeignKey("composition_jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    satisfied = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)


class CompletionNotificationModel(Base):
    __tablename__ = "composition_notifications"
    __table_args__ = (
        UniqueConstraint("job_id", "endpoint_hash", name="uq_composition_notification_browser"),
        Index("ix_composition_notifications_ready", "status", "next_attempt_at"),
    )
    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("composition_jobs.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False)
    endpoint_hash = Column(String(64), nullable=False)
    endpoint = Column(String(4096), nullable=False)
    p256dh = Column(String(128), nullable=False)
    auth = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False)
    attempts = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    next_attempt_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
