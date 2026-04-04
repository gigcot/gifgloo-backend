from sqlalchemy import Column, String, DateTime, JSON

from config.database import Base


class CompositionJobModel(Base):
    __tablename__ = "composition_jobs"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False)
    stage = Column(String, nullable=True)
    gif_url = Column(String, nullable=True)
    source_gif_asset_id = Column(String, nullable=True)
    target_asset_id = Column(String, nullable=True)
    draft_asset_id = Column(String, nullable=True)
    result_asset_id = Column(String, nullable=True)
    result_url = Column(String, nullable=True)
    failed_reason = Column(String, nullable=True)
    durations_ms = Column(JSON, nullable=True)
    spec = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
