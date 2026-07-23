from user.application.ports.outbound.async_user_repository import AsyncUserRepository


class AsyncVerifyUserService:
    def __init__(self, user_repo: AsyncUserRepository):
        self._user_repo = user_repo

    async def execute(self, user_id: str) -> bool:
        user = await self._user_repo.find_by_id(user_id)
        return user is not None and user.is_active()
