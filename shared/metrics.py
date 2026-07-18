import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response as StarletteResponse

from shared.request_context import current_request_path


request_timing_logger = logging.getLogger("gifgloo.request_timing")
request_timing_logger.setLevel(logging.INFO)
request_timing_logger.propagate = False

if not request_timing_logger.handlers:
    request_timing_handler = logging.StreamHandler()
    request_timing_handler.setFormatter(logging.Formatter("%(message)s"))
    request_timing_logger.addHandler(request_timing_handler)


HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests.",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)
HTTP_PRE_APP_WAIT_SECONDS = Histogram(
    "http_pre_app_wait_seconds",
    "Time from Nginx proxy dispatch until FastAPI middleware starts for loadtest requests.",
    ["method", "path"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress.",
    ["method", "path"],
)

SSE_ACTIVE_CONNECTIONS = Gauge(
    "sse_active_connections",
    "Active SSE connections.",
)
SSE_COMPLETED_TOTAL = Counter(
    "sse_completed_total",
    "SSE streams that delivered a completed event.",
)
SSE_FAILED_TOTAL = Counter(
    "sse_failed_total",
    "SSE streams that delivered a failed event.",
)
SSE_DISCONNECT_TOTAL = Counter(
    "sse_disconnect_total",
    "SSE streams disconnected before a terminal event.",
)

COMPOSITION_CREATED_TOTAL = Counter(
    "composition_created_total",
    "Composition jobs created.",
)
COMPOSITION_COMPLETED_TOTAL = Counter(
    "composition_completed_total",
    "Composition jobs completed.",
)
COMPOSITION_FAILED_TOTAL = Counter(
    "composition_failed_total",
    "Composition jobs failed.",
)

PIPELINE_CHECKPOINT_TOTAL = Counter(
    "pipeline_checkpoint_total",
    "Internal pipeline checkpoint callbacks.",
    ["stage"],
)
PIPELINE_COMPLETE_TOTAL = Counter(
    "pipeline_complete_total",
    "Internal pipeline complete callbacks.",
)
PIPELINE_FAIL_TOTAL = Counter(
    "pipeline_fail_total",
    "Internal pipeline fail callbacks.",
)
FAKE_PIPELINE_TRIGGER_TOTAL = Counter(
    "fake_pipeline_trigger_total",
    "Fake pipeline triggers.",
    ["mode"],
)
CREDIT_DEDUCT_TOTAL = Counter(
    "credit_deduct_total",
    "Credit deductions.",
)
CREDIT_REFUND_TOTAL = Counter(
    "credit_refund_total",
    "Credit refunds.",
)
DB_QUERY_TOTAL = Counter(
    "db_query_total",
    "Database queries.",
    ["operation", "status"],
)
DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds.",
    ["operation"],
)
DB_POOL_CHECKOUT_TOTAL = Counter(
    "db_pool_checkout_total",
    "Database pool checkouts.",
    ["pool"],
)
DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "Database connections currently checked out from the SQLAlchemy pool.",
    ["pool"],
)
DB_CONNECTION_HOLD_SECONDS = Histogram(
    "db_connection_hold_seconds",
    "Time a database connection stayed checked out from the SQLAlchemy pool.",
    ["pool", "path"],
)
EVENT_LOOP_LAG_SECONDS = Histogram(
    "event_loop_lag_seconds",
    "Delay between scheduled and actual event loop wake-up.",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10),
)
EVENT_LOOP_LAG_WINDOW_MAX_SECONDS = Gauge(
    "event_loop_lag_window_max_seconds",
    "Maximum event loop wake-up lag observed in the rolling one-minute window.",
)
FASTAPI_THREADPOOL_BORROWED_TOKENS = Gauge(
    "fastapi_threadpool_borrowed_tokens",
    "AnyIO default threadpool tokens currently in use.",
)
FASTAPI_THREADPOOL_TOTAL_TOKENS = Gauge(
    "fastapi_threadpool_total_tokens",
    "AnyIO default threadpool token capacity.",
)


async def monitor_runtime_metrics() -> None:
    import anyio

    loop = asyncio.get_running_loop()
    limiter = anyio.to_thread.current_default_thread_limiter()
    interval_seconds = 0.1
    window_started_at = loop.time()
    window_max_lag_seconds = 0.0
    while True:
        expected_wake_at = loop.time() + interval_seconds
        await asyncio.sleep(interval_seconds)
        now = loop.time()
        lag_seconds = max(0.0, now - expected_wake_at)
        EVENT_LOOP_LAG_SECONDS.observe(lag_seconds)
        if now - window_started_at >= 60:
            window_started_at = now
            window_max_lag_seconds = lag_seconds
        else:
            window_max_lag_seconds = max(window_max_lag_seconds, lag_seconds)
        EVENT_LOOP_LAG_WINDOW_MAX_SECONDS.set(window_max_lag_seconds)
        FASTAPI_THREADPOOL_BORROWED_TOKENS.set(limiter.borrowed_tokens)
        FASTAPI_THREADPOOL_TOTAL_TOKENS.set(limiter.total_tokens)


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route and getattr(route, "path", None):
        return route.path
    return normalized_path(request.url.path)


def normalized_path(path: str) -> str:
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "compositions":
        return "/compositions/{composition_job_id}"
    if len(parts) == 3 and parts[0] == "compositions" and parts[2] == "status":
        return "/compositions/{composition_job_id}/status"
    if len(parts) == 4 and parts[0] == "internal" and parts[1] == "compositions":
        return f"/internal/compositions/{{job_id}}/{parts[3]}"
    return path


def log_loadtest_request(
    request: Request,
    path: str,
    status: int,
    started_at: datetime,
    duration_seconds: float,
    pre_app_wait_seconds: float | None,
) -> None:
    loadtest_run_id = request.headers.get("X-Loadtest-Run-ID")
    if not loadtest_run_id:
        return

    payload = {
        "event": "fastapi_request_completed",
        "request_id": request.headers.get("X-Request-ID", ""),
        "loadtest_run_id": loadtest_run_id,
        "method": request.method,
        "path": path,
        "status": status,
        "started_at": started_at.isoformat(),
        "duration_seconds": round(duration_seconds, 6),
    }
    if pre_app_wait_seconds is not None:
        payload["pre_app_wait_seconds"] = round(pre_app_wait_seconds, 6)
    request_timing_logger.info(json.dumps(payload, separators=(",", ":")))


async def record_http_metrics(
    request: Request,
    call_next: Callable[[Request], Awaitable[StarletteResponse]],
) -> StarletteResponse:
    method = request.method
    in_progress_path = normalized_path(request.url.path)
    if in_progress_path == "/metrics":
        return await call_next(request)

    request_path_token = current_request_path.set(in_progress_path)
    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=in_progress_path).inc()
    started_at = time.perf_counter()
    started_at_utc = datetime.now(timezone.utc)
    pre_app_wait_seconds = None
    nginx_upstream_start = request.headers.get("X-Nginx-Upstream-Start")
    if request.headers.get("X-Loadtest-Run-ID") and nginx_upstream_start:
        pre_app_wait_seconds = max(0.0, time.time() - float(nginx_upstream_start))
        HTTP_PRE_APP_WAIT_SECONDS.labels(method=method, path=in_progress_path).observe(
            pre_app_wait_seconds
        )
    try:
        response = await call_next(request)
    except Exception:
        path = route_path(request)
        duration_seconds = time.perf_counter() - started_at
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status="500").inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)
        log_loadtest_request(
            request,
            path,
            500,
            started_at_utc,
            duration_seconds,
            pre_app_wait_seconds,
        )
        raise
    finally:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=in_progress_path).dec()
        current_request_path.reset(request_path_token)

    path = route_path(request)
    duration_seconds = time.perf_counter() - started_at
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)
    log_loadtest_request(
        request,
        path,
        response.status_code,
        started_at_utc,
        duration_seconds,
        pre_app_wait_seconds,
    )
    return response
