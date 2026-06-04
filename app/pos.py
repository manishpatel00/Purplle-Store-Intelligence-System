"""
app/pos.py — POS transaction loading and visitor correlation for conversion rate.

Challenge spec: visitor with BILLING_QUEUE_JOIN in the 5-minute window before a POS
transaction timestamp counts as converted for that session.
"""

import csv
import os
from datetime import date, datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models import EventDB

LEGACY_STORE_IDS = {"ST1008", "STORE_BLR_002"}
DEFAULT_POS_PATH = os.path.join("data", "pos_transactions.csv")
CORRELATION_WINDOW = timedelta(minutes=5)


def resolve_pos_path() -> str:
    return os.getenv("POS_CSV_PATH", DEFAULT_POS_PATH)


def _parse_order_datetime(order_date: str, order_time: str) -> datetime | None:
    """Parse Purplle CSV date DD-MM-YYYY and time HH:MM:SS."""
    try:
        d = datetime.strptime(order_date.strip(), "%d-%m-%Y").date()
        parts = order_time.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return datetime(d.year, d.month, d.day, hour, minute, second)
    except (ValueError, IndexError):
        return None


def load_pos_orders(csv_path: str | None = None) -> list[dict]:
    """Load deduplicated POS orders from CSV."""
    path = csv_path or resolve_pos_path()
    orders_by_id: dict[str, dict] = {}
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            oid = row.get("order_id", "")
            if oid and oid not in orders_by_id:
                orders_by_id[oid] = row
    return list(orders_by_id.values())


def _store_matches_row(store_id: str, row: dict) -> bool:
    sid = (row.get("store_id") or "").strip()
    if sid == store_id:
        return True
    return store_id == "STORE_BLR_002" and sid == "ST1008"


def orders_for_date(
    orders: list[dict], query_date: date, store_id: str = "STORE_BLR_002"
) -> list[tuple[datetime, str]]:
    """Return (txn_datetime, order_id) for orders on query_date for this store."""
    result = []
    for o in orders:
        if not _store_matches_row(store_id, o):
            continue
        ts = _parse_order_datetime(o.get("order_date", ""), o.get("order_time", ""))
        if ts and ts.date() == query_date:
            result.append((ts, o.get("order_id", "")))
    return result


async def correlate_pos_conversions(
    session: AsyncSession,
    store_id: str,
    query_date: date,
    csv_path: str | None = None,
) -> tuple[int, int, set[str]]:
    """
    Returns (pos_transaction_count, pos_matched_visitors_count, matched_visitor_ids).
    """
    orders = load_pos_orders(csv_path)
    day_orders = orders_for_date(orders, query_date, store_id)
    if not day_orders:
        return 0, 0, set()

    result = await session.execute(
        select(col(EventDB.visitor_id), col(EventDB.timestamp)).where(
            and_(
                col(EventDB.store_id) == store_id,
                col(EventDB.event_type) == "BILLING_QUEUE_JOIN",
                col(EventDB.is_staff) == False,  # noqa: E712
                col(EventDB.timestamp)
                >= datetime(query_date.year, query_date.month, query_date.day),
                col(EventDB.timestamp)
                < datetime(query_date.year, query_date.month, query_date.day) + timedelta(days=1),
            )
        )
    )
    billing_events = result.all()

    matched: set[str] = set()
    for txn_ts, _order_id in day_orders:
        window_start = txn_ts - CORRELATION_WINDOW
        for visitor_id, event_ts in billing_events:
            if window_start <= event_ts <= txn_ts:
                matched.add(visitor_id)

    return len(day_orders), len(matched), matched
