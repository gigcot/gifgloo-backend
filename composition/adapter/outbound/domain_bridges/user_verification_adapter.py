from composition.application.ports.outbound.user_verification_port import UserVerificationPort


class UserVerificationAdapter(UserVerificationPort):
    """
    User 도메인의 Application Service를 호출해서 유저 유효성을 확인한다.
    User 도메인이 구현되면 verify_user_service 를 주입받아 사용한다.
    """

    def __init__(self, verify_user_service):
        self._verify_user_service = verify_user_service

    def is_active_user(self, user_id: str) -> bool:
        return self._verify_user_service.execute(user_id)
