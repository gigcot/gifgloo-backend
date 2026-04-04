from typing import Optional

from sqlalchemy.orm import Session

from asset.adapter.outbound.models import AssetModel
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from shared.asset_category import AssetCategory
from asset.application.dto import AssetDto, AssetResult
from asset.domain.aggregates.asset import AssetStatus, AssetType


class SqlAlchemyAssetRepository(AssetRepositoryPort):
    def __init__(self, session: Session):
        self._session = session

    def save(self, user_id: str, asset_id: str, asset_type: AssetType, category: AssetCategory, storage_url: Optional[str], status: AssetStatus) -> None:
        self._session.add(AssetModel(
            id=asset_id,
            user_id=user_id,
            asset_type=asset_type.value,
            category=category.value,
            storage_url=storage_url,
            status=status.value,
        ))
        self._session.commit()

    def delete(self, user_id: str, asset_id: str) -> None:
        model = self._session.get(AssetModel, asset_id)
        if model and model.user_id == user_id:
            model.status = "DELETED"
            self._session.commit()

    def get_asset_list(self, user_id: str) -> list[AssetDto]:
        models = (
            self._session.query(AssetModel)
            .filter(AssetModel.user_id == user_id, AssetModel.status != "DELETED")
            .all()
        )
        return [
            AssetDto(
                asset_id=m.id,
                asset_type=AssetType(m.asset_type),
                category=AssetCategory(m.category),
                url=m.storage_url or "",
            )
            for m in models
        ]

    def get_url(self, user_id: str, asset_id: str) -> str:
        model = self._session.get(AssetModel, asset_id)
        if not model or model.user_id != user_id:
            raise ValueError("Asset을 찾을 수 없습니다")
        return model.storage_url or ""

    def find_asset_by_id(self, asset_id: str) -> AssetResult:
        model = self._session.get(AssetModel, asset_id)
        if not model:
            raise ValueError("Asset을 찾을 수 없습니다")
        return AssetResult(
            id=model.id,
            user_id=model.user_id,
            asset_type=AssetType(model.asset_type),
            storage_url=model.storage_url or "",
        )

    def update_status(self, asset_id: str, status: AssetStatus) -> None:
        model = self._session.get(AssetModel, asset_id)
        if model:
            model.status = status.value
            self._session.commit()
