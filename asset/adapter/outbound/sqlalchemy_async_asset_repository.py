from sqlalchemy.ext.asyncio import AsyncSession

from asset.adapter.outbound.models import AssetModel
from asset.application.ports.outbound.persistence.async_asset_repository import AsyncAssetRepository
from asset.domain.aggregates.asset import AssetStatus, AssetType
from shared.asset_category import AssetCategory


class SqlAlchemyAsyncAssetRepository(AsyncAssetRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

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
