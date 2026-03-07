from user.application.ports.inbound.deactivate_user import DeactivateUserCommand, DeactivateUserPort
from user.application.ports.outbound.user_repository import UserRepositoryPort


class DeactivateUserService(DeactivateUserPort):
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    def execute(self, command: DeactivateUserCommand) -> None:
        user = self._user_repo.find_by_id(command.user_id)
        if not user:
            raise ValueError("유저를 찾을 수 없습니다")
        user.deactivate()
        self._user_repo.save(user)
