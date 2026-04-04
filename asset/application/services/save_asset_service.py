from asset.application.ports.inbound.save import SaveAssetCommand, SaveAssetPort
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.storage.upload import StorageUploadCommand, StorageUploadPort
from asset.domain.aggregates.asset import Asset, AssetType
from asset.domain.value_objects.storage_url import StorageUrl
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from shared.asset_category import AssetCategory
from shared.exceptions import AuthorizationException, ValidationException
import uuid

_CATEGORY_TO_ASSET_TYPE = {
    AssetCategory.KLIPY_GIF: AssetType.ANIMATED,
    AssetCategory.USER_UPLOAD: AssetType.STATIC,
    AssetCategory.COMPOSITION_DRAFT: AssetType.STATIC,
    AssetCategory.COMPOSITION_RESULT: AssetType.ANIMATED,
}


class SaveAssetService(SaveAssetPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            asset_repo: AssetRepositoryPort,
            external_storage: StorageUploadPort,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo
        self._external_storage = external_storage

    def execute(self, command: SaveAssetCommand) -> str:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        if not command.url and not command.image_data:
            raise ValidationException("url 또는 image_data 중 하나는 필요합니다")

        asset_id = str(uuid.uuid4())
        asset_type = _CATEGORY_TO_ASSET_TYPE[command.category]

        if command.image_data:
            save_result = self._external_storage.execute(
                StorageUploadCommand(asset_id, asset_type, command.image_data)
            )
            storage_url = save_result.storage_url
        else:
            storage_url = command.url

        asset = Asset(
            asset_id,
            command.user_id,
            asset_type,
            StorageUrl(storage_url),
        )

        self._asset_repo.save(
            asset.user_id, asset.id, asset.type,
            command.category, asset.storage_url.value, asset.status,
        )

        return asset_id
