from user.application.ports.inbound.verify_user import VerifyUserPort
from user.application.ports.outbound.user_repository import UserRepositoryPort


class VerifyUserService(VerifyUserPort):
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    def execute(self, user_id: str) -> bool:
        user = self._user_repo.find_by_id(user_id)
        return user is not None and user.is_active()
