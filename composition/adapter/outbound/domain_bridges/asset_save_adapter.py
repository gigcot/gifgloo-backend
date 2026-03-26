from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSavePort, AssetSaveCommand
from asset.application.ports.inbound.save import SaveAssetPort, SaveAssetCommand

_CATEGORY_TO_ASSET_TYPE = {
    "KLIPY_GIF": "ANIMATED",
    "USER_UPLOAD": "STATIC",
    "COMPOSITION_DRAFT": "STATIC",
    "COMPOSITION_RESULT": "ANIMATED",
}


class AssetSaveAdapter(AssetSavePort):
    def __init__(self, asset_service: SaveAssetPort):
        self._asset_service = asset_service

    def save(self, command: AssetSaveCommand) -> str:
        asset_type = _CATEGORY_TO_ASSET_TYPE.get(command.category, "STATIC")
        return self._asset_service.execute(
            SaveAssetCommand(
                user_id=command.user_id,
                category=command.category,
                asset_type=asset_type,
                url=command.url,
                image_data=command.image_data,
            )
        )
