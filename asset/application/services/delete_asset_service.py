from asset.application.ports.inbound.delete import DeleteAssetCommand, DeleteAssetPort
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from shared.exceptions import AuthorizationException



class DeleteAssetService(DeleteAssetPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            asset_repo: AssetRepositoryPort,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo

    def execute(self, command: DeleteAssetCommand):

        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        asset = self._asset_repo.find_by_id(command.asset_id)
        asset.delete(command.user_id)
        self._asset_repo.update(asset)
