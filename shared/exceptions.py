from typing import Any


class DomainException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundException(DomainException):
    """리소스를 찾을 수 없음 → 404"""
    pass


class AuthorizationException(DomainException):
    """접근 권한 없음 → 403"""
    pass


class InvalidStateException(DomainException):
    """상태 전이 불가 → 409"""
    pass


class BusinessRuleException(DomainException):
    """비즈니스 규칙 위반 → 400"""
    pass


class ValidationException(DomainException):
    """입력값 검증 실패 → 422"""
    pass


class ConfirmationRequiredException(DomainException):
    """유저 확인 필요 → 422 + proposal"""

    def __init__(self, message: str, code: str, proposal: dict[str, Any]):
        self.code = code
        self.proposal = proposal
        super().__init__(message)
