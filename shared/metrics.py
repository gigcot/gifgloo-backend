import asyncio
import os
import resource
import sys
import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from starlette.responses import Response as StarletteResponse

from shared.request_context import current_request_path


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
    "Time from Nginx proxy dispatch until FastAPI middleware starts.",
    ["method", "path"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 3, 5, 10, 20),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress.",
    ["method", "path"],
    multiprocess_mode="livesum",
)

SSE_ACTIVE_CONNECTIONS = Gauge(
    "sse_active_connections",
    "Active SSE connections.",
    multiprocess_mode="livesum",
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
    multiprocess_mode="livesum",
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
    multiprocess_mode="livemax",
)
FASTAPI_THREADPOOL_BORROWED_TOKENS = Gauge(
    "fastapi_threadpool_borrowed_tokens",
    "AnyIO default threadpool tokens currently in use.",
    multiprocess_mode="livesum",
)
FASTAPI_THREADPOOL_TOTAL_TOKENS = Gauge(
    "fastapi_threadpool_total_tokens",
    "AnyIO default threadpool token capacity.",
    multiprocess_mode="livesum",
)
FASTAPI_PROCESS_CPU_SECONDS = Counter(
    "fastapi_process_cpu_seconds",
    "CPU time consumed by all live FastAPI worker processes.",
)
FASTAPI_PROCESS_RESIDENT_MEMORY_BYTES = Gauge(
    "fastapi_process_resident_memory_bytes",
    "Resident memory used by all live FastAPI worker processes.",
    multiprocess_mode="livesum",
)
FASTAPI_WORKER_PROCESSES = Gauge(
    "fastapi_worker_processes",
    "Live FastAPI worker processes.",
    multiprocess_mode="livesum",
)


def _resident_memory_bytes() -> int:
    if os.path.exists("/proc/self/statm"):
        with open("/proc/self/statm") as statm:
            resident_pages = int(statm.read().split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE")
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return max_rss if sys.platform == "darwin" else max_rss * 1024


async def monitor_runtime_metrics() -> None:
    import anyio

    loop = asyncio.get_running_loop()
    limiter = anyio.to_thread.current_default_thread_limiter()
    interval_seconds = 0.1
    window_started_at = loop.time()
    window_max_lag_seconds = 0.0
    last_process_cpu_seconds = time.process_time()
    next_memory_sample_at = loop.time()
    FASTAPI_WORKER_PROCESSES.set(1)
    while True:
        expected_wake_at = loop.time() + interval_seconds
        await asyncio.sleep(interval_seconds)
        now = loop.time()
        process_cpu_seconds = time.process_time()
        FASTAPI_PROCESS_CPU_SECONDS.inc(process_cpu_seconds - last_process_cpu_seconds)
        last_process_cpu_seconds = process_cpu_seconds
        if now >= next_memory_sample_at:
            FASTAPI_PROCESS_RESIDENT_MEMORY_BYTES.set(_resident_memory_bytes())
            next_memory_sample_at = now + 1
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
    if "PROMETHEUS_MULTIPROC_DIR" not in os.environ:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


def mark_metrics_process_dead() -> None:
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
        multiprocess.mark_process_dead(os.getpid())


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
    nginx_upstream_start = request.headers.get("X-Nginx-Upstream-Start")
    if nginx_upstream_start:
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
        raise
    finally:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=in_progress_path).dec()
        current_request_path.reset(request_path_token)

    path = route_path(request)
    duration_seconds = time.perf_counter() - started_at
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration_seconds)
    return response
