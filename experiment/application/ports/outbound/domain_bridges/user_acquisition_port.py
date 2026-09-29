from abc import ABC, abstractmethod


class UserAcquisitionPort(ABC):
    @abstractmethod
    async def get_campaign(self, user_id: str) -> str | None:
        pass
