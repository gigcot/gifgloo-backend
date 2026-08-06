from typing import Optional

from sqlalchemy.orm import Session

from asset.adapter.outbound.models import AssetModel
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from shared.asset_category import AssetCategory
from asset.application.dto import AssetDto
from asset.domain.aggregates.asset import Asset, AssetStatus, AssetType
from asset.domain.value_objects.storage_url import StorageUrl
from shared.exceptions import NotFoundException


def _to_domain(model: AssetModel) -> Asset:
    return Asset(
        id=model.id,
        user_id=model.user_id,
        asset_type=AssetType(model.asset_type),
        category=AssetCategory(model.category),
        storage_url=StorageUrl(model.storage_url or ""),
        status=AssetStatus(model.status),
        share_token=model.share_token,
    )


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

    def get_asset_list(self, user_id: str, category: Optional[AssetCategory] = None) -> list[AssetDto]:
        q = self._session.query(AssetModel).filter(
            AssetModel.user_id == user_id, AssetModel.status != "DELETED"
        )
        if category:
            q = q.filter(AssetModel.category == category.value)
        models = q.all()
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

    def find_by_id(self, asset_id: str) -> Asset:
        model = self._session.get(AssetModel, asset_id)
        if not model:
            raise NotFoundException("자산을 찾을 수 없습니다")
        return _to_domain(model)

    def find_by_share_token(self, share_token: str) -> Asset:
        model = self._session.query(AssetModel).filter(AssetModel.share_token == share_token).one_or_none()
        if not model:
            raise NotFoundException("공유 결과를 찾을 수 없습니다")
        return _to_domain(model)

    def update(self, asset: Asset) -> None:
        model = self._session.get(AssetModel, asset.id)
        if not model:
            raise NotFoundException("자산을 찾을 수 없습니다")
        model.status = asset.status.value
        model.share_token = asset.share_token
        self._session.commit()
