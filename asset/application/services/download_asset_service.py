from asset.application.ports.inbound.download_asset import (
    DownloadAssetCommand,
    DownloadAssetPort,
    DownloadAssetResult,
    DownloadSharedAssetPort,
    DownloadSharedAssetQuery,
)
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.storage.download import StorageDownloadCommand, StorageDownloadPort
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from shared.asset_category import AssetCategory
from shared.exceptions import AuthorizationException, NotFoundException


class DownloadAssetService(DownloadAssetPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        asset_repo: AssetRepositoryPort,
        storage: StorageDownloadPort,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo
        self._storage = storage

    def execute(self, command: DownloadAssetCommand) -> DownloadAssetResult:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")
        asset = self._asset_repo.find_by_id(command.asset_id)
        if asset.user_id != command.user_id:
            raise AuthorizationException("자신의 자산만 다운로드할 수 있습니다")
        return DownloadAssetResult(
            data=self._storage.execute(StorageDownloadCommand(asset.storage_url.value)).bytes,
        )


class DownloadSharedAssetService(DownloadSharedAssetPort):
    def __init__(self, asset_repo: AssetRepositoryPort, storage: StorageDownloadPort):
        self._asset_repo = asset_repo
        self._storage = storage

    def execute(self, query: DownloadSharedAssetQuery) -> DownloadAssetResult:
        asset = self._asset_repo.find_by_share_token(query.share_token)
        if asset.category != AssetCategory.COMPOSITION_RESULT or not asset.is_available_for_composition():
            raise NotFoundException("공유 결과를 찾을 수 없습니다")
        return DownloadAssetResult(
            data=self._storage.execute(StorageDownloadCommand(asset.storage_url.value)).bytes,
        )
