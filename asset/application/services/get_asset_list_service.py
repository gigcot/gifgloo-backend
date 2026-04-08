from asset.application.ports.inbound.get_asset_list import GetAssetListCommand, GetAssetListPort, GetAssetListResult
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from shared.exceptions import AuthorizationException


class GetAssetListlService(GetAssetListPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            asset_repo: AssetRepositoryPort,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo

    def execute(self, command: GetAssetListCommand) -> GetAssetListResult:

        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        asset_list = self._asset_repo.get_asset_list(command.user_id, command.category)

        return GetAssetListResult(asset_list)
