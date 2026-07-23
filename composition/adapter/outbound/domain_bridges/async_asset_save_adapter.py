from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSaveCommand, AssetSavePort
from asset.application.services.async_save_asset_from_url_service import AsyncSaveAssetFromUrlService
from shared.exceptions import ValidationException


class AsyncAssetSaveAdapter(AssetSavePort):
    def __init__(self, asset_service: AsyncSaveAssetFromUrlService):
        self._asset_service = asset_service

    async def save(self, command: AssetSaveCommand) -> str:
        if command.url is None:
            raise ValidationException("url은 필요합니다")
        return await self._asset_service.execute(command.user_id, command.category, command.url)
