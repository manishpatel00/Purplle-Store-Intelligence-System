"""
app/metrics.py — GET /stores/{store_id}/metrics
Purplle Store Intelligence API

Core KPIs:
  - unique_visitors: non-staff ENTRY events, REENTRY not double-counted
  - conversion_rate_pct: POS-correlated buyers / unique visitors (5-min billing window)
  - avg_dwell_by_zone_sec: mean dwell time per brand zone
  - current_queue_depth: from latest BILLING_QUEUE_JOIN metadata
  - abandonment_rate_pct: BILLING_QUEUE_ABANDON / BILLING_QUEUE_JOIN
  - hourly_footfall: visitors per hour for footfall heatmap
  - top_zones: zones by visit count (most engaged brand areas)
"""

import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.database import get_session
from app.models import EventDB
from app.pos import correlate_pos_conversions

log = structlog.get_logger()
router = APIRouter(tags=["metrics"])


@router.get("/stores/{store_id}/metrics")
async def get_metrics(
    store_id: str,
    target_date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    session: AsyncSession = Depends(get_session),
):
    """
    Real-time store metrics for a given date.
    All counts exclude staff (is_staff=True).
    Conversion rate = POS-correlated purchasers / unique visitors (challenge spec).
    """
    if target_date:
        try:
            query_date = date.fromisoformat(target_date)
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    # Check if we have any data for this date; if not, try 2026-04-10 (the challenge date)
    has_data = await _has_data_for_date(session, store_id, query_date)
    if not has_data:
        query_date = settings.challenge_date

    # 1. Unique visitors (ENTRY only — REENTRY excluded to avoid double-count)
    unique_visitors = await _count_distinct_visitors(
        session, store_id, "ENTRY", query_date, exclude_staff=True
    )

    # 2. Visitors who reached billing queue (unique, non-staff)
    billing_visitors = await _count_distinct_visitors(
        session, store_id, "BILLING_QUEUE_JOIN", query_date, exclude_staff=True
    )

    # 3. Billing queue abandonment count
    abandon_count = await _count_distinct_visitors(
        session, store_id, "BILLING_QUEUE_ABANDON", query_date, exclude_staff=True
    )

    # 4. POS-correlated conversion (5-min window before each transaction)
    pos_txn_count, pos_matched_visitors, _ = await correlate_pos_conversions(
        session, store_id, query_date
    )

    if pos_txn_count > 0:
        conversion_rate = (
            (pos_matched_visitors / unique_visitors * 100) if unique_visitors > 0 else 0.0
        )
    else:
        # Fallback when no POS rows for this date (e.g. empty test stores)
        conversion_rate = (billing_visitors / unique_visitors * 100) if unique_visitors > 0 else 0.0

    abandonment_rate = (abandon_count / billing_visitors * 100) if billing_visitors > 0 else 0.0

    # 5. Avg dwell per zone (in seconds)
    dwell_by_zone = await _avg_dwell_by_zone(session, store_id, query_date)

    # 6. Current queue depth from latest event metadata
    current_queue_depth = await _get_current_queue_depth(session, store_id, query_date)

    # 7. Hourly footfall
    hourly_footfall = await _hourly_footfall(session, store_id, query_date)

    # 8. Top zones by visit count
    top_zones = await _top_zones(session, store_id, query_date, limit=5)

    # 9. Total re-entries today
    reentry_count = await _count_events(session, store_id, "REENTRY", query_date)

    log.info(
        "metrics.computed",
        store_id=store_id,
        date=str(query_date),
        visitors=unique_visitors,
        conversion=round(conversion_rate, 2),
        pos_matched=pos_matched_visitors,
    )

    return {
        "store_id": store_id,
        "date": str(query_date),
        "unique_visitors": unique_visitors,
        "conversion_rate_pct": round(conversion_rate, 2),
        "conversion_method": "pos_correlated" if pos_txn_count > 0 else "billing_proxy",
        "pos_transaction_count": pos_txn_count,
        "pos_matched_visitors": pos_matched_visitors,
        "avg_dwell_by_zone_sec": dwell_by_zone,
        "current_queue_depth": current_queue_depth,
        "abandonment_rate_pct": round(abandonment_rate, 2),
        "billing_visitors": billing_visitors,
        "hourly_footfall": hourly_footfall,
        "top_zones_by_visits": top_zones,
        "reentry_count": reentry_count,
        "computed_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Helper queries
# ---------------------------------------------------------------------------


async def _has_data_for_date(session, store_id: str, d: date) -> bool:
    result = await session.execute(
        select(func.count(EventDB.id)).where(
            and_(
                EventDB.store_id == store_id,
                func.date(EventDB.timestamp) == d,
            )
        )
    )
    return (result.scalar_one() or 0) > 0


async def _count_distinct_visitors(
    session, store_id: str, event_type: str, d: date, exclude_staff: bool = True
) -> int:
    conditions = [
        EventDB.store_id == store_id,
        EventDB.event_type == event_type,
        func.date(EventDB.timestamp) == d,
    ]
    if exclude_staff:
        conditions.append(EventDB.is_staff == False)  # noqa: E712

    result = await session.execute(
        select(func.count(func.distinct(EventDB.visitor_id))).where(and_(*conditions))
    )
    return result.scalar_one() or 0


async def _count_events(session, store_id: str, event_type: str, d: date) -> int:
    result = await session.execute(
        select(func.count(EventDB.id)).where(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type == event_type,
                func.date(EventDB.timestamp) == d,
            )
        )
    )
    return result.scalar_one() or 0


def _load_configured_zones(store_id: str) -> list[str]:
    try:
        filepath = os.path.join(os.getcwd(), "store_layout.json")
        if os.path.exists(filepath):
            with open(filepath) as f:
                data = json.load(f)
                if data.get("store_id") == store_id:
                    return [
                        z["zone_id"]
                        for z in data.get("zones", [])
                        if z.get("zone_id") != "ENTRY_EXIT"
                    ]
    except Exception:
        pass
    # Fallback to standard zones list if loading fails
    return [
        "EB_KOREAN",
        "THE_FACE_SHOP",
        "GOOD_VIBES",
        "DERMDOC",
        "MINIMALIST",
        "AQUALOGICA",
        "LAKME_SKIN",
        "ACCESSORIES",
        "MAYBELLINE",
        "FACES_CANADA",
        "LAKME_MAKEUP",
        "COLORBAR_SUGAR",
        "SWISS_BEAUTY",
        "NY_BAE",
        "ALPS_GOODNESS",
        "STREAX",
        "FOH",
        "FRAGRANCE",
        "NAIL_UNIT",
        "MAKEUP_UNIT",
        "CASH_COUNTER",
        "BILLING_QUEUE",
    ]


async def _avg_dwell_by_zone(session, store_id: str, d: date) -> dict:
    result = await session.execute(
        select(EventDB.zone_id, func.avg(EventDB.dwell_ms))
        .where(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type.in_(["ZONE_EXIT", "ZONE_DWELL"]),
                EventDB.is_staff == False,  # noqa: E712
                EventDB.zone_id.isnot(None),
                EventDB.dwell_ms > 0,
                func.date(EventDB.timestamp) == d,
            )
        )
        .group_by(EventDB.zone_id)
        .order_by(func.avg(EventDB.dwell_ms).desc())
    )
    rows = result.all()

    # Initialize all configured zones with 0.0 dwell time
    configured = _load_configured_zones(store_id)
    dwell_map = {zone: 0.0 for zone in configured}

    # Fill in actual values from query
    for row in rows:
        if row[0]:
            dwell_map[row[0]] = round(row[1] / 1000, 1)

    return dwell_map


async def _get_current_queue_depth(session, store_id: str, d: date) -> int:
    result = await session.execute(
        select(EventDB.metadata_json)
        .where(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type == "BILLING_QUEUE_JOIN",
                func.date(EventDB.timestamp) == d,
            )
        )
        .order_by(EventDB.timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        try:
            meta = json.loads(row)
            return meta.get("queue_depth", 0) or 0
        except Exception:
            pass
    return 0


async def _hourly_footfall(session, store_id: str, d: date) -> dict:
    """Returns {hour_str: visitor_count} for the given date (cross-DB compatible)."""
    result = await session.execute(
        select(
            EventDB.timestamp,
            EventDB.visitor_id,
        ).where(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type == "ENTRY",
                EventDB.is_staff == False,  # noqa: E712
                func.date(EventDB.timestamp) == d,
            )
        )
    )
    rows = result.all()
    # Group by hour in Python for cross-DB compatibility (no func.strftime)
    hour_visitors: dict[str, set[str]] = defaultdict(set)
    for ts, vid in rows:
        hour_key = ts.strftime("%H") if hasattr(ts, "strftime") else str(ts)[:2]
        hour_visitors[hour_key].add(vid)
    return {h: len(vids) for h, vids in sorted(hour_visitors.items())}


async def _top_zones(session, store_id: str, d: date, limit: int = 5) -> list:
    """Return top N zones by number of unique visitors."""
    result = await session.execute(
        select(
            EventDB.zone_id,
            func.count(func.distinct(EventDB.visitor_id)).label("visits"),
        )
        .where(
            and_(
                EventDB.store_id == store_id,
                EventDB.event_type == "ZONE_ENTER",
                EventDB.is_staff == False,  # noqa: E712
                EventDB.zone_id.isnot(None),
                func.date(EventDB.timestamp) == d,
            )
        )
        .group_by(EventDB.zone_id)
        .order_by(func.count(func.distinct(EventDB.visitor_id)).desc())
        .limit(limit)
    )
    rows = result.all()
    return [{"zone_id": row[0], "unique_visitors": row[1]} for row in rows]
