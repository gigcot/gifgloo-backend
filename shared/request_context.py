from contextvars import ContextVar


current_request_path: ContextVar[str] = ContextVar(
    "current_request_path",
    default="unknown",
)
