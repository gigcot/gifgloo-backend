import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.exceptions import (
    DomainException,
    NotFoundException,
    AuthenticationException,
    AuthorizationException,
    InvalidStateException,
    BusinessRuleException,
    InsufficientCreditException,
    ValidationException,
    PayloadTooLargeException,
    ExternalServiceException,
    ConfirmationRequiredException,
    CompositionUnavailableException,
)

STATUS_MAP: dict[type[DomainException], int] = {
    NotFoundException: 404,
    AuthenticationException: 401,
    AuthorizationException: 403,
    InvalidStateException: 409,
    BusinessRuleException: 400,
    InsufficientCreditException: 402,
    ValidationException: 422,
    PayloadTooLargeException: 413,
    ExternalServiceException: 502,
    ConfirmationRequiredException: 422,
    CompositionUnavailableException: 429,
}


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(CompositionUnavailableException)
    async def composition_unavailable_handler(request: Request, exc: CompositionUnavailableException):
        headers = (
            {"Retry-After": str(exc.retry_after_seconds)}
            if exc.retry_after_seconds is not None
            else None
        )
        return JSONResponse(
            status_code=429,
            headers=headers,
            content={"error": "COMPOSITION_UNAVAILABLE", "message": exc.message},
        )

    @app.exception_handler(ConfirmationRequiredException)
    async def confirmation_handler(request: Request, exc: ConfirmationRequiredException):
        return JSONResponse(
            status_code=422,
            content={
                "error": "CONFIRMATION_REQUIRED",
                "code": exc.code,
                "message": exc.message,
                "proposal": exc.proposal,
            },
        )

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        status_code = STATUS_MAP.get(type(exc), 400)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": type(exc).__name__,
                "message": exc.message,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger = logging.getLogger(__name__)
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "서버 오류가 발생했습니다",
            },
        )
