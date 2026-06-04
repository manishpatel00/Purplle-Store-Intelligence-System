"""
app/health.py — GET /health
Purplle Store Intelligence API

Returns API + database status and per-store event feed freshness.
A store is marked STALE_FEED if last event is > 10 minutes old.
"""

from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import EventDB

log = structlog.get_logger()
router = APIRouter(tags=["health"])

STALE_THRESHOLD_MINUTES = 10


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """
    System health check.
    Returns 200 with {"status": "healthy"} when all systems are operational.
    Degraded when database is unreachable.
    """
    now = datetime.now(UTC)
    stale_cutoff = now - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    store_statuses = {}
    db_status = "ok"

    try:
        result = await session.execute(
            select(EventDB.store_id, func.max(EventDB.timestamp)).group_by(EventDB.store_id)
        )
        rows = result.all()

        for store_id, last_ts in rows:
            if last_ts is None:
                feed_status = "NO_DATA"
            elif last_ts.tzinfo is None:
                # SQLite returns naive datetime — make aware
                last_ts_aware = last_ts.replace(tzinfo=UTC)
                feed_status = "STALE_FEED" if last_ts_aware < stale_cutoff else "OK"
            else:
                feed_status = "STALE_FEED" if last_ts < stale_cutoff else "OK"

            store_statuses[store_id] = {
                "last_event_at": last_ts.isoformat() if last_ts else None,
                "feed_status": feed_status,
            }

    except Exception as e:
        db_status = f"error: {str(e)}"
        log.error("health.db_error", error=str(e))

    overall = "healthy" if db_status == "ok" else "degraded"

    return {
        "status": overall,
        "version": "1.0.0",
        "database": db_status,
        "stores": store_statuses,
        "checked_at": now.isoformat(),
    }
