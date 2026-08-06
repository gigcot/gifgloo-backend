import secrets

from asset.application.ports.inbound.create_share_link import (
    CreateShareLinkCommand,
    CreateShareLinkPort,
    CreateShareLinkResult,
)
from asset.application.ports.outbound.persistence.asset_repository import AssetRepositoryPort
from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from shared.exceptions import AuthorizationException


class CreateShareLinkService(CreateShareLinkPort):
    def __init__(
        self,
        user_verification: UserVerificationPort,
        asset_repo: AssetRepositoryPort,
    ):
        self._user_verification = user_verification
        self._asset_repo = asset_repo

    def execute(self, command: CreateShareLinkCommand) -> CreateShareLinkResult:
        if not self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")

        asset = self._asset_repo.find_by_id(command.asset_id)
        if asset.user_id != command.user_id:
            raise AuthorizationException("자신의 자산만 공유할 수 있습니다")

        asset.enable_sharing(secrets.token_urlsafe(24))
        self._asset_repo.update(asset)
        return CreateShareLinkResult(share_token=asset.share_token)
