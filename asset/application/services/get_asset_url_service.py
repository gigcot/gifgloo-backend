from asset.application.ports.inbound.get_asset_url import GetAssetUrlCommand, GetAssetUrlPort, GetAssetUrlResult
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from asset.domain.aggregates.asset import Asset


class GetAssetUrlService(GetAssetUrlPort):
    def __init__(
            self,
            user_verification: UserVerificationPort,
            asset_repo: AssetRepositoryPort,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo

    def execute(self, command: GetAssetUrlCommand) -> GetAssetUrlResult:

        if not self._user_verification.is_active_user(command.user_id):
            raise ValueError("유효하지 않은 유저입니다")

        asset = self._asset_repo.find_asset_by_id(command.asset_id)

        asset_obj = Asset(asset.id, asset.user_id, asset.asset_type, asset.storage_url)

        if asset_obj.is_available_for_composition():
            return GetAssetUrlResult(asset_obj.storage_url.value)
        else:
            raise ValueError("해당 이미지는 사용 불가한 상태입니다")
        

