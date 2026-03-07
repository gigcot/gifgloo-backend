from asset.application.ports.outbound.user_verification_port import UserVerificationPort
from user.application.services.verify_user_service import VerifyUserService


class UserVerificationAdapter(UserVerificationPort):

    def __init__(self, verify_user_service: VerifyUserService):
        self._verify_user_service = verify_user_service

    def is_active_user(self, user_id: str) -> bool:
        return self._verify_user_service.execute(user_id)
