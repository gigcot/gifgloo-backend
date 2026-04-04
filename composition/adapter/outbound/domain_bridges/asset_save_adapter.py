from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSavePort, AssetSaveCommand
from asset.application.ports.inbound.save import SaveAssetPort, SaveAssetCommand


class AssetSaveAdapter(AssetSavePort):
    def __init__(self, asset_service: SaveAssetPort):
        self._asset_service = asset_service

    def save(self, command: AssetSaveCommand) -> str:
        return self._asset_service.execute(
            SaveAssetCommand(
                user_id=command.user_id,
                category=command.category,
                url=command.url,
                image_data=command.image_data,
            )
        )
