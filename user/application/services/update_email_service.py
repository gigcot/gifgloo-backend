from user.application.ports.inbound.update_email import UpdateEmailCommand, UpdateEmailPort
from user.application.ports.outbound.user_repository import UserRepositoryPort
from user.domain.value_objects.email import Email
from shared.exceptions import NotFoundException


class UpdateEmailService(UpdateEmailPort):
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    def execute(self, command: UpdateEmailCommand) -> None:
        user = self._user_repo.find_by_id(command.user_id)
        if not user:
            raise NotFoundException("유저를 찾을 수 없습니다")
        user.update_email(Email(command.email))
        self._user_repo.save(user)
