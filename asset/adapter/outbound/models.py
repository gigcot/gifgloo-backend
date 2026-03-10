from sqlalchemy import Column, String

from config.database import Base


class AssetModel(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    asset_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    storage_url = Column(String, nullable=True)
    status = Column(String, nullable=False)
