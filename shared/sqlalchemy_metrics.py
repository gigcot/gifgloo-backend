import time

from sqlalchemy import Engine, event
from sqlalchemy.engine import ExecutionContext

from shared.metrics import (
    DB_POOL_CHECKED_OUT,
    DB_POOL_CHECKOUT_TOTAL,
    DB_QUERY_DURATION_SECONDS,
    DB_QUERY_TOTAL,
)


def _operation(statement: str | None) -> str:
    if not statement:
        return "UNKNOWN"
    parts = statement.lstrip().split(None, 1)
    if not parts:
        return "UNKNOWN"
    return parts[0].upper()


def register_sqlalchemy_metrics(engine: Engine) -> None:
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn,
        cursor,
        statement: str,
        parameters,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        context._gifgloo_query_started_at = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(
        conn,
        cursor,
        statement: str,
        parameters,
        context: ExecutionContext,
        executemany: bool,
    ) -> None:
        started_at = context._gifgloo_query_started_at
        operation = _operation(statement)
        DB_QUERY_DURATION_SECONDS.labels(operation=operation).observe(
            time.perf_counter() - started_at
        )
        DB_QUERY_TOTAL.labels(operation=operation, status="ok").inc()

    @event.listens_for(engine, "handle_error")
    def handle_error(exception_context) -> None:
        operation = _operation(exception_context.statement)
        DB_QUERY_TOTAL.labels(operation=operation, status="error").inc()

    @event.listens_for(engine, "checkout")
    def checkout(dbapi_connection, connection_record, connection_proxy) -> None:
        DB_POOL_CHECKOUT_TOTAL.inc()
        DB_POOL_CHECKED_OUT.inc()

    @event.listens_for(engine, "checkin")
    def checkin(dbapi_connection, connection_record) -> None:
        DB_POOL_CHECKED_OUT.dec()
