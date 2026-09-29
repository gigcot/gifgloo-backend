from experiment.application.ports.outbound.domain_bridges.user_acquisition_port import (
    UserAcquisitionPort,
)
from user.application.services.get_user_acquisition_campaign_service import (
    GetUserAcquisitionCampaignService,
)


class UserAcquisitionAdapter(UserAcquisitionPort):
    def __init__(self, service: GetUserAcquisitionCampaignService):
        self._service = service

    async def get_campaign(self, user_id: str) -> str | None:
        return await self._service.execute(user_id)
