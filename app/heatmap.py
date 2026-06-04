"""
app/heatmap.py — GET /stores/{store_id}/heatmap

Zone visit frequency, average dwell, and normalized intensity (0–100) for grid rendering.
All configured zones appear even when visits=0. data_confidence is LOW when <20 sessions.
"""

from datetime import date
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.core.settings import settings
from app.database import get_session
from app.metrics import _has_data_for_date, _load_configured_zones
from app.models import EventDB

log = structlog.get_logger()
router = APIRouter(tags=["heatmap"])


@router.get("/stores/{store_id}/heatmap")
async def get_heatmap(
    store_id: str,
    target_date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    session: AsyncSession = Depends(get_session),
):
    """Zone heatmap: visits, dwell, intensity 0–100; empty zones included."""
    if target_date:
        try:
            query_date = date.fromisoformat(target_date)
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    if not await _has_data_for_date(session, store_id, query_date):
        query_date = settings.challenge_date

    base = and_(
        col(EventDB.store_id) == store_id,
        col(EventDB.is_staff) == False,  # noqa: E712
        func.date(col(EventDB.timestamp)) == query_date,
    )

    visit_rows = (
        await session.execute(
            select(
                col(EventDB.zone_id),
                func.count(func.distinct(col(EventDB.visitor_id))).label("visits"),
            )
            .where(
                and_(
                    base,
                    col(EventDB.event_type) == "ZONE_ENTER",
                    col(EventDB.zone_id).isnot(None),
                )
            )
            .group_by(col(EventDB.zone_id))
        )
    ).all()

    dwell_rows = (
        await session.execute(
            select(
                col(EventDB.zone_id),
                func.avg(col(EventDB.dwell_ms)).label("avg_dwell"),
            )
            .where(
                and_(
                    base,
                    col(EventDB.event_type).in_(["ZONE_EXIT", "ZONE_DWELL"]),
                    col(EventDB.zone_id).isnot(None),
                    col(EventDB.dwell_ms) > 0,
                )
            )
            .group_by(col(EventDB.zone_id))
        )
    ).all()

    visits_map = {r[0]: int(r[1]) for r in visit_rows if r[0]}
    dwell_map = {r[0]: int(r[1] or 0) for r in dwell_rows if r[0]}

    session_count = (
        await session.execute(
            select(func.count(func.distinct(col(EventDB.visitor_id)))).where(
                and_(base, col(EventDB.event_type) == "ENTRY")
            )
        )
    ).scalar_one() or 0

    data_confidence = "HIGH" if session_count >= 20 else "LOW"
    configured = _load_configured_zones(store_id)
    max_visits = max(visits_map.values(), default=0)

    zones: list[dict[str, Any]] = []
    for zone_id in configured:
        visits = visits_map.get(zone_id, 0)
        avg_dwell_ms = dwell_map.get(zone_id, 0)
        intensity = round(100 * visits / max(max_visits, 1)) if max_visits else 0
        zones.append(
            {
                "zone_id": zone_id,
                "visits": visits,
                "avg_dwell_ms": avg_dwell_ms,
                "avg_dwell_sec": round(avg_dwell_ms / 1000, 1),
                "intensity": intensity,
            }
        )

    zones.sort(key=lambda z: int(z["intensity"]), reverse=True)

    log.info(
        "heatmap.computed",
        store_id=store_id,
        date=str(query_date),
        zones=len(zones),
        sessions=session_count,
        confidence=data_confidence,
    )

    return {
        "store_id": store_id,
        "date": str(query_date),
        "session_count": session_count,
        "data_confidence": data_confidence,
        "zones": zones,
    }
