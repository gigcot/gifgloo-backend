from user.application.ports.outbound.async_user_repository import AsyncUserRepository


class GetUserAcquisitionCampaignService:
    def __init__(self, user_repo: AsyncUserRepository):
        self._user_repo = user_repo

    async def execute(self, user_id: str) -> str | None:
        user = await self._user_repo.find_by_id(user_id)
        if user is None or user.acquisition is None:
            return None
        return user.acquisition.campaign
