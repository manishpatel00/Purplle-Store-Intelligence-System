"""
app/main.py — FastAPI application entrypoint
Purplle Store Intelligence API v1.0.0

Architecture:
  - FastAPI with lifespan for startup/shutdown
  - SQLite/PostgreSQL (async) via SQLModel
  - Structured logging via structlog (JSON format)
  - Trace IDs on every request (X-Trace-ID header) propagated via ContextVars
  - Global 500 handler to prevent stack trace leaks
"""

import asyncio
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.anomalies import router as anomaly_router
from app.core.settings import settings
from app.core.tracing import add_trace_id, set_trace_id
from app.database import init_db
from app.funnel import router as funnel_router
from app.health import router as health_router
from app.heatmap import router as heatmap_router
from app.ingestion import router as ingest_router
from app.metrics import router as metrics_router
from app.metrics_prom import router as prom_router
from app.websocket import router as ws_router
from app.worker import consume_stream

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_trace_id,  # structlog processor picks up context trace_id automatically
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """DB init on startup; graceful shutdown log on exit."""
    global worker_task
    await init_db()

    # Start Redis Stream worker only if not in testing environment
    if settings.environment != "testing":
        worker_task = asyncio.create_task(consume_stream())

    log.info("api.started", version="1.0.0", environment=settings.environment)
    yield
    if worker_task:
        worker_task.cancel()
    log.info("api.shutdown")


# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Purplle Store Intelligence API",
    description=(
        "Real-time analytics API for Purplle retail stores. "
        "Processes CCTV-derived events to compute footfall, conversion, "
        "zone dwell, billing queue depth, and anomalies."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration — strictly allow dashboard origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID"],
)


# ---------------------------------------------------------------------------
# Middleware: trace ID + request logging
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())[:8]
    set_trace_id(trace_id)
    start = time.perf_counter()

    response = await call_next(request)

    latency_ms = round((time.perf_counter() - start) * 1000, 2)
    store_id = request.path_params.get("store_id", "-")

    log.info(
        "http.request",
        trace_id=trace_id,
        method=request.method,
        path=str(request.url.path),
        store_id=store_id,
        status=response.status_code,
        latency_ms=latency_ms,
    )

    response.headers["X-Trace-ID"] = trace_id
    response.headers["X-API-Version"] = "1.0.0"
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Mount production versioned routes under /api/v1/
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(ingest_router)
api_v1.include_router(metrics_router)
api_v1.include_router(funnel_router)
api_v1.include_router(anomaly_router)
api_v1.include_router(heatmap_router)

app.include_router(api_v1)

# Challenge spec paths (no /api/v1 prefix) for reviewers and run.sh
legacy = APIRouter()
legacy.include_router(ingest_router)
legacy.include_router(metrics_router)
legacy.include_router(funnel_router)
legacy.include_router(anomaly_router)
legacy.include_router(heatmap_router)
app.include_router(legacy)
app.include_router(health_router)
app.include_router(ws_router)
app.include_router(prom_router)


# ---------------------------------------------------------------------------
# Global error handler — never leak stack traces
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(
        "unhandled_error",
        error=str(exc),
        error_type=type(exc).__name__,
        path=str(request.url.path),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Check server logs.",
        },
    )


# ---------------------------------------------------------------------------
# Root info
# ---------------------------------------------------------------------------


@app.get("/", tags=["root"])
async def root():
    return {
        "service": "Purplle Store Intelligence API",
        "version": "1.0.0",
        "store": "Brigade Road, Bangalore (STORE_BLR_002 / ST1008)",
        "endpoints": {
            "ingest": "/api/v1/events/ingest",
            "metrics": "/api/v1/stores/{store_id}/metrics",
            "funnel": "/api/v1/stores/{store_id}/funnel",
            "anomalies": "/api/v1/stores/{store_id}/anomalies",
            "heatmap": "/api/v1/stores/{store_id}/heatmap",
            "health": "/health",
            "docs": "/docs",
        },
    }
