from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from asset.adapter.outbound.models import AssetModel
from asset.application.ports.outbound.persistence.async_asset_repository import AsyncAssetRepository
from asset.domain.aggregates.asset import AssetStatus, AssetType
from asset.domain.value_objects.asset_list_item import AssetListItem
from shared.asset_category import AssetCategory


class SqlAlchemyAsyncAssetRepository(AsyncAssetRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_all_by_user_id(
        self,
        user_id: str,
        category: AssetCategory | None,
        limit: int,
        offset: int,
    ) -> list[AssetListItem]:
        statement = select(AssetModel).where(
            AssetModel.user_id == user_id,
            AssetModel.status != AssetStatus.DELETED.value,
        )
        if category:
            statement = statement.where(AssetModel.category == category.value)
        statement = statement.order_by(AssetModel.id).limit(limit).offset(offset)
        models = (await self._session.scalars(statement)).all()
        return [
            AssetListItem(
                asset_id=model.id,
                asset_type=AssetType(model.asset_type),
                category=AssetCategory(model.category),
                url=model.storage_url or "",
            )
            for model in models
        ]

    async def save(
        self,
        user_id: str,
        asset_id: str,
        asset_type: AssetType,
        category: AssetCategory,
        storage_url: str,
        status: AssetStatus,
    ) -> None:
        self._session.add(AssetModel(
            id=asset_id,
            user_id=user_id,
            asset_type=asset_type.value,
            category=category.value,
            storage_url=storage_url,
            status=status.value,
        ))
        await self._session.flush()
