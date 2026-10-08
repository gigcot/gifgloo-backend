import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv(".env")

from config.payment_settings import validate_payment_config
from config.web_push import get_web_push_settings, dispatch_completion_notifications
from shared.fastapi_error_handler import register_error_handlers
from shared.logging_config import configure_file_logging
from shared.metrics import (
    metrics_response,
    mark_metrics_process_dead,
    monitor_runtime_metrics,
    record_http_metrics,
)
from shared.request_context import RequestContextMiddleware
from user.adapter.inbound.fastapi.session_middleware import UserSessionMiddleware
import user.adapter.outbound.persistence.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import asset.adapter.outbound.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401
import payment.adapter.outbound.persistence.models  # noqa: F401
import admin.adapter.outbound.persistence.models  # noqa: F401
import experiment.adapter.outbound.persistence.models  # noqa: F401

from composition.adapter.inbound.fastapi.composition_router import router as composition_router
from composition.adapter.inbound.fastapi.completion_notification_router import router as completion_notification_router
from composition.adapter.inbound.fastapi.composition_internal_router import router as composition_internal_router
from user.adapter.inbound.fastapi.oauth2 import router as oauth_router
from user.adapter.inbound.fastapi.user_router import router as user_router
from asset.adapter.inbound.fastapi.asset_router import router as asset_router
from credit_account.adapter.inbound.fastapi.credit_account_router import router as credit_router
from payment.adapter.inbound.fastapi.payment_router import router as payment_router
from admin.adapter.inbound.fastapi.admin_router import router as admin_router
from experiment.adapter.inbound.fastapi.experiment_router import router as experiment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_payment_config()
    runtime_metrics_task = asyncio.create_task(monitor_runtime_metrics())
    push_settings = get_web_push_settings()
    push_task = asyncio.create_task(dispatch_completion_notifications(push_settings)) if push_settings else None
    try:
        yield
    finally:
        if push_task:
            push_task.cancel()
            with suppress(asyncio.CancelledError):
                await push_task
        runtime_metrics_task.cancel()
        with suppress(asyncio.CancelledError):
            await runtime_metrics_task
        mark_metrics_process_dead()


configure_file_logging()

app = FastAPI(lifespan=lifespan)
register_error_handlers(app)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(UserSessionMiddleware)

CORS_ORIGINS = os.getenv("CORS_ORIGINS").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-Request-ID"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    return await record_http_metrics(request, call_next)


app.get("/metrics")(metrics_response)
app.include_router(composition_router)
app.include_router(completion_notification_router)
app.include_router(composition_internal_router)
app.include_router(oauth_router)
app.include_router(user_router)
app.include_router(asset_router)
app.include_router(credit_router)
app.include_router(payment_router)
app.include_router(admin_router)
app.include_router(experiment_router)
