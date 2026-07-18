from abc import ABC, abstractmethod

from composition.application.ports.outbound.domain_bridges.asset_save_port import AssetSaveCommand


class AsyncAssetSavePort(ABC):
    @abstractmethod
    async def save(self, command: AssetSaveCommand) -> str:
        pass
