from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship

from config.database import Base


class CompositionJobModel(Base):
    __tablename__ = "composition_jobs"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    base_image_asset_id = Column(String, nullable=False)
    base_image_role = Column(String, nullable=False)
    base_image_format = Column(String, nullable=False)
    overlay_image_asset_id = Column(String, nullable=False)
    overlay_image_role = Column(String, nullable=False)
    overlay_image_format = Column(String, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    result_asset_id = Column(String, nullable=True)
    failed_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    frames = relationship("CompositionFrameModel", back_populates="job", cascade="all, delete-orphan")


class CompositionFrameModel(Base):
    __tablename__ = "composition_frames"

    id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey("composition_jobs.id"), nullable=False)
    frame_index = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    result_asset_id = Column(String, nullable=True)
    failed_reason = Column(String, nullable=True)

    job = relationship("CompositionJobModel", back_populates="frames")
