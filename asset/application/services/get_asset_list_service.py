from asset.application.dto import AssetDto
from asset.application.ports.inbound.get_asset_list import (
    GetAssetListCommand,
    GetAssetListPort,
    GetAssetListResult,
)
from asset.application.ports.outbound.async_user_verification_port import AsyncUserVerificationPort
from asset.application.ports.outbound.persistence.async_asset_repository import AsyncAssetRepository
from shared.exceptions import AuthorizationException


class GetAssetListService(GetAssetListPort):
    def __init__(
            self,
            user_verification: AsyncUserVerificationPort,
            asset_repo: AsyncAssetRepository,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo

    async def execute(self, command: GetAssetListCommand) -> GetAssetListResult:

        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        items = await self._asset_repo.find_all_by_user_id(
            command.user_id,
            command.category,
            command.limit,
            command.offset,
        )

        return GetAssetListResult(
            [
                AssetDto(
                    asset_id=item.asset_id,
                    asset_type=item.asset_type,
                    category=item.category,
                    url=item.url,
                )
                for item in items
            ]
        )
