from typing import Optional

from sqlalchemy.orm import Session

from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.dto import AssetCategory, AssetDto, AssetResult


class SqlAlchemyAssetRepository(AssetRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, user_id: str, asset_id: str, asset_type: str, category: AssetCategory, storage_url: Optional[str], status: str) -> None:
        raise NotImplementedError

    def delete(self, user_id: str, asset_id: str) -> None:
        raise NotImplementedError
    
    def get_asset_list(self, user_id: str) -> list[AssetDto]:
        raise NotImplementedError
    
    def get_url(self, user_id: str, asset_id:str) -> str:
        raise NotImplementedError
    
    def find_asset_by_id(self, asset_id: str) -> AssetResult:
        raise NotImplementedError
    
    def update_status(self, asset_id: str, status: str) -> None:
        raise NotImplementedError
