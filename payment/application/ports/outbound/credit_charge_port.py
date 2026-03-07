from abc import ABC, abstractmethod

class ChargeCreditPort(ABC):
    @abstractmethod
    def charge(self, user_id, amount) -> None:
        pass
