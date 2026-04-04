from user.application.ports.inbound.change_role import ChangeRoleCommand, ChangeRolePort
from user.application.ports.outbound.user_repository import UserRepositoryPort
from shared.exceptions import NotFoundException


class ChangeRoleService(ChangeRolePort):
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    def execute(self, command: ChangeRoleCommand) -> None:
        user = self._user_repo.find_by_id(command.target_user_id)
        if not user:
            raise NotFoundException("유저를 찾을 수 없습니다")
        user.change_role(command.new_role)
        self._user_repo.save(user)
