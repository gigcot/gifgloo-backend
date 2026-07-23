from asset.application.services.async_create_asset_from_url_service import (
    AsyncCreateAssetFromUrlService,
)
from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSaveCommand, AssetSavePort
from shared.exceptions import ValidationException


class AsyncAssetCreateAdapter(AssetSavePort):
    def __init__(self, asset_service: AsyncCreateAssetFromUrlService):
        self._asset_service = asset_service

    async def save(self, command: AssetSaveCommand) -> str:
        if command.url is None:
            raise ValidationException("url은 필요합니다")
        return await self._asset_service.execute(command.user_id, command.category, command.url)
