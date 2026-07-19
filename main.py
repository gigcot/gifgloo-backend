import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import httpx
load_dotenv(".env.loadtest")
os.environ.setdefault("DB_POOL_PRE_PING", "false")
os.environ.setdefault("ASYNC_DB_POOL_SIZE", "8")
os.environ.setdefault("ASYNC_DB_MAX_OVERFLOW", "2")

from config.database import engine, Base
from shared.fastapi_error_handler import register_error_handlers
from shared.metrics import (
    metrics_response,
    monitor_runtime_metrics,
    record_http_metrics,
    start_request_timing_log_listener,
    stop_request_timing_log_listener,
)
from config.composition_loadtest import create_pipeline_trigger
import user.adapter.outbound.persistence.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import asset.adapter.outbound.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401

from composition.adapter.inbound.fastapi.composition_router import router as composition_router
from composition.adapter.inbound.fastapi.composition_internal_router import router as composition_internal_router
from user.adapter.inbound.fastapi.oauth2 import router as oauth_router
from user.adapter.inbound.fastapi.user_router import router as user_router
from asset.adapter.inbound.fastapi.asset_router import router as asset_router
from credit_account.adapter.inbound.fastapi.credit_account_router import router as credit_router

is_shutting_down = False


def _handle_sigterm(*_):
    global is_shutting_down
    is_shutting_down = True


signal.signal(signal.SIGTERM, _handle_sigterm)


async def _recover_processing_jobs() -> None:
    return


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_request_timing_log_listener()
    http_client = httpx.AsyncClient(timeout=30)
    pipeline_trigger = create_pipeline_trigger(http_client)
    app.state.pipeline_trigger = pipeline_trigger
    runtime_metrics_task = asyncio.create_task(monitor_runtime_metrics())
    try:
        await _recover_processing_jobs()
        yield
    finally:
        runtime_metrics_task.cancel()
        with suppress(asyncio.CancelledError):
            await runtime_metrics_task
        await pipeline_trigger.aclose()
        await http_client.aclose()
        stop_request_timing_log_listener()


Base.metadata.create_all(bind=engine)

app = FastAPI(lifespan=lifespan)
logging.getLogger("uvicorn.access").disabled = (
    os.getenv("LOADTEST_UVICORN_ACCESS_LOG", "false").lower() != "true"
)
register_error_handlers(app)

CORS_ORIGINS = os.getenv("CORS_ORIGINS").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    return await record_http_metrics(request, call_next)


@app.middleware("http")
async def shutdown_guard(request: Request, call_next):
    if is_shutting_down and request.method == "POST" and request.url.path == "/compositions":
        return JSONResponse({"detail": "서버가 재시작 중입니다. 잠시 후 다시 시도해주세요."}, status_code=503)
    return await call_next(request)


app.get("/metrics")(metrics_response)
app.include_router(composition_router)
app.include_router(composition_internal_router)
app.include_router(oauth_router)
app.include_router(user_router)
app.include_router(asset_router)
app.include_router(credit_router)
