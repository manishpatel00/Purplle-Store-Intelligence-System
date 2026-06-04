"""
app/metrics_prom.py — Prometheus metrics endpoint configuration
"""

from fastapi import APIRouter, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.core.settings import settings

router = APIRouter(tags=["prometheus"])

# Metrics definitions
events_ingested_total = Counter(
    "si_events_ingested_total", "Events ingested", ["store_id", "event_type"]
)
ingest_latency = Histogram("si_ingest_latency_seconds", "Ingest request latency", ["store_id"])
active_sessions_gauge = Gauge("si_active_sessions", "Currently open visitor sessions", ["store_id"])
queue_depth_gauge = Gauge("si_queue_depth", "Current billing queue depth", ["store_id", "zone_id"])
api_errors_total = Counter("si_api_errors_total", "API errors by code", ["code"])


@router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    """Exposes Prometheus-compatible metric scrapes."""
    if not settings.prometheus_enabled:
        raise HTTPException(status_code=404, detail="Prometheus metrics are disabled")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
