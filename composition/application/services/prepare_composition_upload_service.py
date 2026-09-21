from composition.application.ports.outbound.aws.upload_staging_port import (
    PrepareUploadCommand,
    PrepareUploadResult,
    UploadStagingPort,
)
from composition.application.ports.outbound.domain_bridges.user_verification_port import UserVerificationPort
from shared.exceptions import AuthorizationException


class PrepareCompositionUploadService:
    def __init__(self, user_verification: UserVerificationPort, upload_staging: UploadStagingPort):
        self._user_verification = user_verification
        self._upload_staging = upload_staging

    async def execute(self, command: PrepareUploadCommand) -> PrepareUploadResult:
        if not await self._user_verification.is_active_user(command.user_id):
            raise AuthorizationException("유효하지 않은 유저입니다")
        return await self._upload_staging.prepare(command)
