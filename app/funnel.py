"""
app/funnel.py — GET /stores/{store_id}/funnel
Purplle Store Intelligence API

4-stage conversion funnel:
  Entry -> Zone Visit -> Billing Queue -> Purchase

Each stage shows count + drop-off percentage from previous stage.
All stages exclude staff.
"""

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.database import get_session
from app.metrics import _has_data_for_date
from app.models import EventDB

log = structlog.get_logger()
router = APIRouter(tags=["funnel"])


@router.get("/stores/{store_id}/funnel")
async def get_funnel(
    store_id: str,
    target_date: str | None = Query(None, description="YYYY-MM-DD, defaults to today"),
    session: AsyncSession = Depends(get_session),
):
    """
    Visitor conversion funnel for a store.

    Stages:
      1. Entry: unique non-staff visitors (ENTRY events, not REENTRY)
      2. Zone Visit: visitors who entered at least one product zone
      3. Billing Queue: visitors who joined billing queue
      4. Purchase: billing joiners who did NOT abandon (completed purchase)

    Returns stage counts + drop-off % at each transition.
    """
    if target_date:
        try:
            query_date = date.fromisoformat(target_date)
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    # Fallback to challenge date if no data today
    has_data = await _has_data_for_date(session, store_id, query_date)
    if not has_data:
        query_date = settings.challenge_date

    def base_where(*extra):
        return and_(
            EventDB.store_id == store_id,
            EventDB.is_staff == False,  # noqa: E712
            func.date(EventDB.timestamp) == query_date,
            *extra,
        )

    # Stage 1: Total unique visitors (ENTRY — not REENTRY)
    entry_count = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                base_where(EventDB.event_type == "ENTRY")
            )
        )
    ).scalar_one() or 0

    # Stage 2: Visitors who entered at least one zone
    zone_count = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                base_where(EventDB.event_type == "ZONE_ENTER")
            )
        )
    ).scalar_one() or 0

    # Stage 3: Visitors who joined billing queue
    billing_count = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                base_where(EventDB.event_type == "BILLING_QUEUE_JOIN")
            )
        )
    ).scalar_one() or 0

    # Stage 4: Purchasers = billing joiners who did NOT abandon
    abandon_count = (
        await session.execute(
            select(func.count(func.distinct(EventDB.visitor_id))).where(
                base_where(EventDB.event_type == "BILLING_QUEUE_ABANDON")
            )
        )
    ).scalar_one() or 0

    # Purchasers = joined billing - abandoned
    # (visitors who joined AND abandoned are not purchasers)
    purchase_count = max(0, billing_count - abandon_count)

    def dropoff_pct(current: int, previous: int) -> float:
        if previous == 0:
            return 0.0
        return round((1 - current / previous) * 100, 1)

    funnel_stages = [
        {
            "stage": "entry",
            "label": "Store Entry",
            "count": entry_count,
            "dropoff_pct": 0.0,
            "conversion_from_entry_pct": 100.0,
        },
        {
            "stage": "zone_visit",
            "label": "Product Zone Visit",
            "count": zone_count,
            "dropoff_pct": dropoff_pct(zone_count, entry_count),
            "conversion_from_entry_pct": round(
                (zone_count / entry_count * 100) if entry_count else 0, 1
            ),
        },
        {
            "stage": "billing_queue",
            "label": "Billing Queue",
            "count": billing_count,
            "dropoff_pct": dropoff_pct(billing_count, zone_count),
            "conversion_from_entry_pct": round(
                (billing_count / entry_count * 100) if entry_count else 0, 1
            ),
        },
        {
            "stage": "purchase",
            "label": "Completed Purchase",
            "count": purchase_count,
            "dropoff_pct": dropoff_pct(purchase_count, billing_count),
            "conversion_from_entry_pct": round(
                (purchase_count / entry_count * 100) if entry_count else 0, 1
            ),
        },
    ]

    log.info(
        "funnel.computed",
        store_id=store_id,
        date=str(query_date),
        entry=entry_count,
        zone=zone_count,
        billing=billing_count,
        purchase=purchase_count,
    )

    return {
        "store_id": store_id,
        "date": str(query_date),
        "funnel": funnel_stages,
        "overall_conversion_rate_pct": round(
            (purchase_count / entry_count * 100) if entry_count > 0 else 0.0, 2
        ),
    }
