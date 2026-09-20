from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String

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
