from sqlalchemy import Column, String, DateTime

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
