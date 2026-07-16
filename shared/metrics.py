import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
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
    try:
        response = await call_next(request)
    except Exception:
        path = route_path(request)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status="500").inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(
            time.perf_counter() - started_at
        )
        raise
    finally:
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=in_progress_path).dec()
        current_request_path.reset(request_path_token)

    path = route_path(request)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(
        time.perf_counter() - started_at
    )
    return response
