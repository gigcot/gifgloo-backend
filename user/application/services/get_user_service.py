from user.application.ports.inbound.get_user import GetUserPort, GetUserQuery, GetUserResult
from user.application.ports.outbound.user_repository import UserRepositoryPort
from shared.exceptions import NotFoundException


class GetUserService(GetUserPort):
    def __init__(self, user_repo: UserRepositoryPort):
        self._user_repo = user_repo

    def execute(self, query: GetUserQuery) -> GetUserResult:
        user = self._user_repo.find_by_id(query.user_id)
        if not user:
            raise NotFoundException("유저를 찾을 수 없습니다")
        return GetUserResult(
            user_id=user.id,
            email=user.email.value if user.email else None,
            role=user.role,
            status=user.status,
        )
