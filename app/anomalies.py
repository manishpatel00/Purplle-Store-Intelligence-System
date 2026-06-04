"""
app/anomalies.py — GET /stores/{store_id}/anomalies
Purplle Store Intelligence API

Detects operational anomalies in real-time:
  1. BILLING_QUEUE_SPIKE — queue depth > 5 (critical at > 8)
  2. HIGH_ABANDONMENT — billing abandonment > 30%
  3. DEAD_ZONE — no zone visits in last 30 minutes
  4. LOW_FOOTFALL — visitors well below hourly average
  5. STALE_FEED — no events received in last 10 minutes

Severity levels: INFO | WARN | CRITICAL
"""

from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.database import get_session
from app.metrics import _get_current_queue_depth, _has_data_for_date
from app.models import EventDB, VisitorSessionDB

log = structlog.get_logger()
router = APIRouter(tags=["anomalies"])


@router.get("/stores/{store_id}/anomalies")
async def get_anomalies(
    store_id: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Return list of active anomalies for a store.
    Checks are run on-demand (not cached).
    Each anomaly has: anomaly_id, severity, message, suggested_action, detected_at.
    """
    try:
        dialect_name = session.bind.dialect.name if session.bind else ""
    except Exception:
        dialect_name = ""
    if dialect_name == "postgresql":
        await session.execute(text("SET LOCAL statement_timeout = 5000"))

    anomalies = []
    now = datetime.now(UTC).replace(tzinfo=None)  # naive UTC for TIMESTAMP WITHOUT TIME ZONE
    today = date.today()

    # Determine working date
    has_today = await _has_data_for_date(session, store_id, today)
    query_date = today if has_today else settings.challenge_date

    # ------------------------------------------------------------------
    # 1. Billing queue spike
    # ------------------------------------------------------------------
    queue_depth = await _get_current_queue_depth(session, store_id, query_date)
    if queue_depth > 5:
        severity = "CRITICAL" if queue_depth > 8 else "WARN"
        anomalies.append(
            {
                "anomaly_id": "BILLING_QUEUE_SPIKE",
                "anomaly_type": "BILLING_QUEUE_SPIKE",
                "severity": severity,
                "message": f"Billing queue depth is {queue_depth} (threshold: 5)",
                "suggested_action": "Open additional billing counter or redirect staff to assist",
                "queue_depth": queue_depth,
                "detected_at": now.isoformat(),
            }
        )

    # ------------------------------------------------------------------
    # 2. High abandonment rate (> 30%)
    # ------------------------------------------------------------------
    billing_count, abandon_count = await _get_billing_abandonment(session, store_id, query_date)
    if billing_count > 0:
        abandon_pct = abandon_count / billing_count * 100
        if abandon_pct > 30:
            anomalies.append(
                {
                    "anomaly_id": "HIGH_ABANDONMENT",
                    "anomaly_type": "HIGH_ABANDONMENT",
                    "severity": "WARN",
                    "message": f"Billing queue abandonment at {round(abandon_pct, 1)}% (threshold: 30%)",
                    "suggested_action": "Investigate wait time; consider staff reallocation to billing",
                    "abandonment_pct": round(abandon_pct, 1),
                    "detected_at": now.isoformat(),
                }
            )

    # ------------------------------------------------------------------
    # 3. Dead zone — no zone visits in last 30 minutes
    # ------------------------------------------------------------------
    thirty_min_ago = now - timedelta(minutes=30)
    zone_activity = await _count_recent_events(session, store_id, "ZONE_ENTER", thirty_min_ago)
    if zone_activity == 0:
        anomalies.append(
            {
                "anomaly_id": "DEAD_ZONE",
                "anomaly_type": "DEAD_ZONE",
                "severity": "INFO",
                "message": "No product zone visits in the last 30 minutes",
                "suggested_action": "Check if store is in expected low-traffic period; verify floor camera feed",
                "detected_at": now.isoformat(),
            }
        )

    # ------------------------------------------------------------------
    # 4. Stale feed — no events at all in last 10 minutes
    # ------------------------------------------------------------------
    ten_min_ago = now - timedelta(minutes=10)
    recent_events = await _count_recent_events(session, store_id, None, ten_min_ago)
    if recent_events == 0:
        anomalies.append(
            {
                "anomaly_id": "STALE_FEED",
                "anomaly_type": "STALE_FEED",
                "severity": "WARN",
                "message": "No events received from any camera in the last 10 minutes",
                "suggested_action": "Check CCTV pipeline health; verify cameras are online",
                "detected_at": now.isoformat(),
            }
        )

    # ------------------------------------------------------------------
    # 5. Low footfall vs hourly average
    # ------------------------------------------------------------------
    low_footfall_anomaly = await _check_low_footfall(session, store_id, query_date, now)
    if low_footfall_anomaly:
        anomalies.append(low_footfall_anomaly)

    # ------------------------------------------------------------------
    # 6. Conversion drop (today's rate vs 7-day average)
    # ------------------------------------------------------------------
    conversion_anomaly = await _check_conversion_drop(session, store_id, query_date, now)
    if conversion_anomaly:
        anomalies.append(conversion_anomaly)

    log.info("anomalies.checked", store_id=store_id, count=len(anomalies))

    return {
        "store_id": store_id,
        "active_anomalies": anomalies,
        "anomaly_count": len(anomalies),
        "checked_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Helper queries
# ---------------------------------------------------------------------------


async def _get_billing_abandonment(session, store_id: str, d: date):
    billing = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                and_(
                    EventDB.store_id == store_id,
                    EventDB.event_type == "BILLING_QUEUE_JOIN",
                    EventDB.is_staff == False,  # noqa: E712
                    func.date(EventDB.timestamp) == d,
                )
            )
        )
    ).scalar_one() or 0

    abandon = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                and_(
                    EventDB.store_id == store_id,
                    EventDB.event_type == "BILLING_QUEUE_ABANDON",
                    EventDB.is_staff == False,  # noqa: E712
                    func.date(EventDB.timestamp) == d,
                )
            )
        )
    ).scalar_one() or 0

    return billing, abandon


async def _count_recent_events(session, store_id: str, event_type, since: datetime) -> int:
    conditions = [
        EventDB.store_id == store_id,
        EventDB.timestamp >= since,
    ]
    if event_type:
        conditions.append(EventDB.event_type == event_type)

    result = await session.execute(select(func.count(EventDB.id)).where(and_(*conditions)))
    return result.scalar_one() or 0


async def _check_low_footfall(session, store_id: str, d: date, now: datetime) -> dict | None:
    """Detect current hour footfall < 50% of daily average."""
    current_h = now.hour

    # Current hour visitor count — use timestamp range instead of strftime for cross-DB compatibility
    hour_start = datetime.combine(d, dt_time(current_h, 0, 0))  # naive
    hour_end = datetime.combine(d, dt_time(current_h, 59, 59))  # naive

    current_hour_count = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                and_(
                    EventDB.store_id == store_id,
                    EventDB.event_type == "ENTRY",
                    EventDB.is_staff == False,  # noqa: E712
                    EventDB.timestamp >= hour_start,
                    EventDB.timestamp <= hour_end,
                )
            )
        )
    ).scalar_one() or 0

    # Average hourly count across all hours today
    total_visitors = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                and_(
                    EventDB.store_id == store_id,
                    EventDB.event_type == "ENTRY",
                    EventDB.is_staff == False,  # noqa: E712
                    func.date(EventDB.timestamp) == d,
                )
            )
        )
    ).scalar_one() or 0

    # Store is open ~12 hours; avoid false alerts in off-hours
    store_open_hour = 10
    store_close_hour = 22
    if current_h < store_open_hour or current_h >= store_close_hour:
        return None

    hours_passed = max(1, current_h - store_open_hour + 1)
    avg_hourly = total_visitors / hours_passed

    if avg_hourly > 5 and current_hour_count < avg_hourly * 0.5:
        return {
            "anomaly_id": "LOW_FOOTFALL",
            "anomaly_type": "LOW_FOOTFALL",
            "severity": "INFO",
            "message": f"Hour {current_h:02d}:00 footfall ({current_hour_count}) is below 50% of hourly average ({round(avg_hourly, 1)})",
            "suggested_action": "Consider promotional activity or check if external factors (rain, event) are affecting footfall",
            "current_hour_count": current_hour_count,
            "hourly_average": round(avg_hourly, 1),
            "detected_at": now.isoformat(),
        }

    return None


async def _check_conversion_drop(
    session, store_id: str, query_date: date, now: datetime
) -> dict | None:
    """Compare today's conversion rate vs trailing 7-day average."""
    today_start = datetime.combine(query_date, datetime.min.time())  # naive
    today_end = datetime.combine(query_date, datetime.max.time())  # naive

    # Today's sessions
    today_sessions = (
        await session.execute(
            select(func.count(VisitorSessionDB.id)).where(
                and_(
                    VisitorSessionDB.store_id == store_id,
                    VisitorSessionDB.is_staff.is_(False),
                    VisitorSessionDB.started_at >= today_start,
                    VisitorSessionDB.started_at <= today_end,
                )
            )
        )
    ).scalar_one() or 0

    if today_sessions == 0:
        return None

    today_converted = (
        await session.execute(
            select(func.count(VisitorSessionDB.id)).where(
                and_(
                    VisitorSessionDB.store_id == store_id,
                    VisitorSessionDB.is_staff.is_(False),
                    VisitorSessionDB.converted.is_(True),
                    VisitorSessionDB.started_at >= today_start,
                    VisitorSessionDB.started_at <= today_end,
                )
            )
        )
    ).scalar_one() or 0

    today_rate = today_converted / today_sessions * 100.0

    # Trailing 7 days sessions
    trailing_start = today_start - timedelta(days=7)
    trailing_end = today_start

    trailing_sessions = (
        await session.execute(
            select(func.count(VisitorSessionDB.id)).where(
                and_(
                    VisitorSessionDB.store_id == store_id,
                    VisitorSessionDB.is_staff.is_(False),
                    VisitorSessionDB.started_at >= trailing_start,
                    VisitorSessionDB.started_at < trailing_end,
                )
            )
        )
    ).scalar_one() or 0

    if trailing_sessions == 0:
        return None

    trailing_converted = (
        await session.execute(
            select(func.count(VisitorSessionDB.id)).where(
                and_(
                    VisitorSessionDB.store_id == store_id,
                    VisitorSessionDB.is_staff.is_(False),
                    VisitorSessionDB.converted.is_(True),
                    VisitorSessionDB.started_at >= trailing_start,
                    VisitorSessionDB.started_at < trailing_end,
                )
            )
        )
    ).scalar_one() or 0

    trailing_rate = trailing_converted / trailing_sessions * 100.0

    # Trigger anomaly if today's conversion rate is less than 80% of the trailing average
    if today_rate < trailing_rate * 0.80:
        return {
            "anomaly_id": "CONVERSION_DROP",
            "anomaly_type": "CONVERSION_DROP",
            "severity": "WARN",
            "message": f"Today's conversion rate is {round(today_rate, 1)}%, which is below the 7-day average of {round(trailing_rate, 1)}%",
            "suggested_action": "Check for billing service delays or product zone pricing issues",
            "today_rate": round(today_rate, 1),
            "trailing_rate": round(trailing_rate, 1),
            "detected_at": now.isoformat(),
        }

    return None
