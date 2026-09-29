from abc import ABC, abstractmethod


class CompositionCompletionPort(ABC):
    @abstractmethod
    async def has_completed(self, user_id: str) -> bool:
        pass
