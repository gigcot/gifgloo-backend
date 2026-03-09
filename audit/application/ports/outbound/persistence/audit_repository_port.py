from abc import ABC, abstractmethod


class AuditRepositoryPort(ABC):
    
    @abstractmethod
    def save(self) -> None:
        pass
    
    @abstractmethod
    def find_log_by_id(self) -> ...:
        pass
    
    @abstractmethod
    def find_logs_by_user_id(self) -> ...:
        pass