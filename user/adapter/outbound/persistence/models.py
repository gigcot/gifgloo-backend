from sqlalchemy import Boolean, Column, DateTime, String

from config.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    provider_id = Column(String, nullable=False, index=True)
    email = Column(String, nullable=True)
    role = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
    terms_version = Column(String, nullable=True)
    privacy_version = Column(String, nullable=True)
    is_fourteen_or_older = Column(Boolean, nullable=False, default=False)
    consented_at = Column(DateTime(timezone=True), nullable=True)
