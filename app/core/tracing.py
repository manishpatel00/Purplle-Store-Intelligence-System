"""
app/core/tracing.py — Trace context propagation via ContextVars
"""

from contextvars import ContextVar

_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    """Retrieve the current request trace ID."""
    return _trace_id.get()


def set_trace_id(tid: str) -> None:
    """Set the trace ID for the current context."""
    _trace_id.set(tid)


def add_trace_id(logger, method, event_dict):
    """structlog processor to automatically append trace_id if set."""
    tid = get_trace_id()
    if tid:
        event_dict["trace_id"] = tid
    return event_dict
