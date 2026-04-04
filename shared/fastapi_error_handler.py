import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.exceptions import (
    DomainException,
    NotFoundException,
    AuthorizationException,
    InvalidStateException,
    BusinessRuleException,
    ValidationException,
    ConfirmationRequiredException,
)

STATUS_MAP: dict[type[DomainException], int] = {
    NotFoundException: 404,
    AuthorizationException: 403,
    InvalidStateException: 409,
    BusinessRuleException: 400,
    ValidationException: 422,
    ConfirmationRequiredException: 422,
}


def register_error_handlers(app: FastAPI) -> None:

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
