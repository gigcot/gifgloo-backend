from asset.application.dto import AssetCategory
from asset.application.ports.inbound.save import SaveAssetCommand, SaveAssetPort
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.storage.upload import StorageUploadCommand, StorageUploadPort
from asset.domain.aggregates.asset import Asset
from asset.domain.value_objects.storage_url import StorageUrl
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
import uuid

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

    def execute(self, command: SaveAssetCommand):
        if not self._user_verification.is_active_user(command.user_id):
            raise ValueError("유효하지 않은 유저입니다")
        
        category = command.category
        
        if category == AssetCategory.EXTERNAL and not command.url:
            raise ValueError("url을 찾을 수 없습니다")
        if category == AssetCategory.INTERNAL and not command.image_data:
            raise ValueError("imagedata(bytes)를 찾을 수 없습니다")

        asset_id = str(uuid.uuid4())
        storage_url = None

        if category == AssetCategory.INTERNAL:
            save_result = self._external_storage.execute(StorageUploadCommand(asset_id, command.asset_type, command.image_data))
            storage_url = save_result.storage_url
        
        asset = Asset(
            asset_id,
            command.user_id,
            command.asset_type,
            StorageUrl(storage_url or command.url)
        )
        

        self._asset_repo.save(asset.user_id, asset.id, asset.type, command.category, asset.storage_url.value, asset.status)
