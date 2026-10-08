from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, UniqueConstraint

from config.database import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_users_social_account"),
        CheckConstraint("(provider IS NULL) = (provider_id IS NULL)", name="ck_users_social_pair"),
    )

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=True)
    provider_id = Column(String, nullable=True, index=True)
    session_version = Column(Integer, nullable=False, default=0, server_default="0")
    email = Column(String, nullable=True)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    terms_version = Column(String, nullable=True)
    privacy_version = Column(String, nullable=True)
    is_fourteen_or_older = Column(Boolean, nullable=False, default=False)
    consented_at = Column(DateTime(timezone=True), nullable=True)
    acquisition_source = Column(String(100), nullable=True)
    acquisition_medium = Column(String(100), nullable=True)
    acquisition_campaign = Column(String(100), nullable=True)
    acquisition_content = Column(String(100), nullable=True)
