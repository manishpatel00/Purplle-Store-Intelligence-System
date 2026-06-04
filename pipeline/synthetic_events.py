"""
pipeline/synthetic_events.py — Generates synthetic store events from POS data
Purplle Store Intelligence Challenge 2026

Used as fallback when real CCTV clips are unavailable (e.g., testing).
Derives realistic visitor timelines from POS transaction timestamps.

Logic:
  - Each POS order = 1 confirmed buyer
  - Assume 16% conversion rate → total_visitors = orders / 0.16
  - Spread visitors across store hours using POS transaction density as weight
  - Simulate visitor journeys: ENTRY -> ZONE_ENTER(s) -> BILLING_QUEUE_JOIN -> EXIT
  - 10% abandonment rate for billing queue
  - 5% re-entry rate
"""

import csv
import random
from datetime import UTC, datetime, timedelta

from pipeline.emit import build_event

STORE_HOURS_START = 10  # 10:00 AM
STORE_HOURS_END = 22  # 10:00 PM

# Zone visit probability weights by brand/category from POS data
BRAND_TO_ZONE = {
    "Faces Canada": "FACES_CANADA",
    "Good Vibes": "GOOD_VIBES",
    "NY Bae": "NY_BAE",
    "DERMDOC": "DERMDOC",
    "Maybelline": "MAYBELLINE",
    "Minimalist": "MINIMALIST",
    "Swiss Beauty": "SWISS_BEAUTY",
    "Alps Goodness": "ALPS_GOODNESS",
    "Carmesi": "ACCESSORIES",
    "Round Lab": "EB_KOREAN",
    "Lakme": "LAKME_MAKEUP",
    "Aqualogica": "AQUALOGICA",
    "Colorbar": "COLORBAR_SUGAR",
}

ZONE_POOL = [
    "FOH",
    "FACES_CANADA",
    "GOOD_VIBES",
    "NY_BAE",
    "DERMDOC",
    "MAYBELLINE",
    "MINIMALIST",
    "SWISS_BEAUTY",
    "FRAGRANCE",
    "NAIL_UNIT",
    "LAKME_SKIN",
    "EB_KOREAN",
]


def generate_from_pos(pos_csv_path: str, store_id: str) -> list[dict]:
    """
    Generate synthetic JSONL events from POS transaction CSV.
    Returns list of event dicts sorted by timestamp.
    """
    orders = _load_pos_data(pos_csv_path)
    print(f"[SYNTHETIC] Loaded {len(orders)} POS orders from {pos_csv_path}")

    all_events = []
    visitor_counter = 0

    # Estimate total visitors from 16% conversion rate
    total_buyers = len(orders)
    total_visitors = int(total_buyers / 0.16)
    non_buyer_visitors = total_visitors - total_buyers
    print(
        f"[SYNTHETIC] Estimated visitors: {total_visitors} ({total_buyers} buyers, {non_buyer_visitors} browsers)"
    )

    # Build hourly traffic weights from POS timestamps
    hour_weights = _compute_hour_weights(orders)

    # Generate buyer visitor sessions
    for order in orders:
        visitor_counter += 1
        visitor_id = f"VIS_{visitor_counter:06x}"
        events = _generate_buyer_journey(
            visitor_id=visitor_id,
            store_id=store_id,
            order=order,
        )
        all_events.extend(events)

    # Generate browser (non-buyer) sessions
    base_date = _get_base_date(orders)
    for _ in range(non_buyer_visitors):
        visitor_counter += 1
        visitor_id = f"VIS_{visitor_counter:06x}"
        entry_time = _sample_timestamp(base_date, hour_weights)
        events = _generate_browser_journey(
            visitor_id=visitor_id,
            store_id=store_id,
            entry_time=entry_time,
        )
        all_events.extend(events)

    # Generate re-entry events (5% of visitors return)
    reentry_count = max(1, int(total_visitors * 0.05))
    for i in range(reentry_count):
        # Pick a random existing buyer visitor to re-enter
        visitor_id = f"VIS_{(i % total_buyers + 1):06x}"
        base_t = datetime.now(UTC).replace(
            hour=14, minute=random.randint(0, 59), second=random.randint(0, 59)
        )
        all_events.append(
            build_event(
                event_type="REENTRY",
                store_id=store_id,
                camera_id="CAM_1",
                visitor_id=visitor_id,
                timestamp=base_t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                is_staff=False,
                confidence=0.82,
                session_seq=2,
            )
        )

    # Sort by timestamp
    all_events.sort(key=lambda e: e["timestamp"])
    print(f"[SYNTHETIC] Generated {len(all_events)} events total")
    return all_events


def _load_pos_data(csv_path: str) -> list[dict]:
    """Load and deduplicate POS orders."""
    orders_by_id = {}
    try:
        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                oid = row.get("order_id", "")
                if oid and oid not in orders_by_id:
                    orders_by_id[oid] = row
    except FileNotFoundError:
        print(f"[WARN] POS file not found: {csv_path} — using minimal synthetic data")
        return _minimal_orders()
    return list(orders_by_id.values())


def _minimal_orders() -> list[dict]:
    """Minimal fallback when CSV is unavailable."""
    base = "2026-04-10"
    times = ["12:30:00", "13:15:00", "15:45:00", "16:55:00", "19:21:00", "20:10:00"]
    return [
        {
            "order_id": f"ORD_{i}",
            "order_date": base,
            "order_time": t,
            "brand_name": "Good Vibes",
            "GMV": "500",
            "store_id": "ST1008",
            "store_name": "Brigade_Bangalore",
        }
        for i, t in enumerate(times)
    ]


def _get_base_date(orders: list[dict]) -> str:
    for o in orders:
        d = o.get("order_date", "")
        if d:
            return d
    return "2026-04-10"


def _compute_hour_weights(orders: list[dict]) -> dict:
    """Build hour -> count weight from POS timestamps."""
    weights = {}
    for o in orders:
        t = o.get("order_time", "")
        if t:
            h = int(t.split(":")[0])
            weights[h] = weights.get(h, 0) + 1
    if not weights:
        # Default distribution: 10am-10pm uniform
        weights = {h: 1 for h in range(STORE_HOURS_START, STORE_HOURS_END)}
    return weights


def _sample_timestamp(date_str: str, hour_weights: dict) -> datetime:
    """Sample a random timestamp weighted by hourly traffic."""
    try:
        d = datetime.strptime(date_str, "%d-%m-%Y")
    except ValueError:
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            d = datetime(2026, 4, 10)

    hours = list(hour_weights.keys())
    weights = list(hour_weights.values())
    total = sum(weights)
    norm = [w / total for w in weights]
    chosen_hour = random.choices(hours, weights=norm)[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)

    ts = d.replace(hour=chosen_hour, minute=minute, second=second, tzinfo=UTC)
    return ts


def _generate_buyer_journey(visitor_id: str, store_id: str, order: dict) -> list[dict]:
    """Simulate a full buyer journey: ENTRY -> zones -> BILLING_QUEUE_JOIN -> EXIT."""
    events = []
    camera_id = "CAM_1"

    # Parse order time
    try:
        date_str = order.get("order_date", "10-04-2026")
        time_str = order.get("order_time", "12:00:00")
        try:
            d = datetime.strptime(date_str, "%d-%m-%Y")
        except ValueError:
            d = datetime.strptime(date_str, "%Y-%m-%d")
        purchase_time = d.replace(
            hour=int(time_str.split(":")[0]),
            minute=int(time_str.split(":")[1]),
            second=int(time_str.split(":")[2]),
            tzinfo=UTC,
        )
    except Exception:
        purchase_time = datetime(2026, 4, 10, 14, 0, 0, tzinfo=UTC)

    # Entry time = 15-45 min before purchase
    browse_mins = random.randint(15, 45)
    entry_time = purchase_time - timedelta(minutes=browse_mins)

    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # ENTRY
    events.append(
        build_event(
            event_type="ENTRY",
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            timestamp=fmt(entry_time),
            is_staff=False,
            confidence=round(random.uniform(0.80, 0.97), 3),
            session_seq=1,
        )
    )

    # Visit 1-3 zones
    brand = order.get("brand_name", "")
    primary_zone = BRAND_TO_ZONE.get(brand, random.choice(ZONE_POOL))
    visited_zones = [primary_zone]
    extra = random.randint(0, 2)
    others = [z for z in ZONE_POOL if z != primary_zone]
    random.shuffle(others)
    visited_zones.extend(others[:extra])

    t = entry_time + timedelta(minutes=random.randint(1, 3))
    for zone in visited_zones:
        dwell = random.randint(60, 300)  # 1-5 min dwell

        events.append(
            build_event(
                event_type="ZONE_ENTER",
                store_id=store_id,
                camera_id="CAM_2",
                visitor_id=visitor_id,
                timestamp=fmt(t),
                zone_id=zone,
                is_staff=False,
                confidence=round(random.uniform(0.75, 0.95), 3),
                session_seq=1,
            )
        )

        t += timedelta(seconds=dwell)

        events.append(
            build_event(
                event_type="ZONE_EXIT",
                store_id=store_id,
                camera_id="CAM_2",
                visitor_id=visitor_id,
                timestamp=fmt(t),
                zone_id=zone,
                dwell_ms=dwell * 1000,
                is_staff=False,
                confidence=round(random.uniform(0.75, 0.95), 3),
                session_seq=1,
            )
        )

        t += timedelta(seconds=random.randint(10, 60))

    # Billing queue (buyer always joins)
    queue_depth = random.randint(1, 4)
    events.append(
        build_event(
            event_type="BILLING_QUEUE_JOIN",
            store_id=store_id,
            camera_id="CAM_5",
            visitor_id=visitor_id,
            timestamp=fmt(purchase_time - timedelta(minutes=random.randint(2, 8))),
            zone_id="CASH_COUNTER",
            is_staff=False,
            confidence=round(random.uniform(0.85, 0.97), 3),
            queue_depth=queue_depth,
            session_seq=1,
        )
    )

    # EXIT
    exit_time = purchase_time + timedelta(minutes=random.randint(2, 7))
    events.append(
        build_event(
            event_type="EXIT",
            store_id=store_id,
            camera_id=camera_id,
            visitor_id=visitor_id,
            timestamp=fmt(exit_time),
            is_staff=False,
            confidence=round(random.uniform(0.80, 0.96), 3),
            session_seq=1,
        )
    )

    return events


def _generate_browser_journey(visitor_id: str, store_id: str, entry_time: datetime) -> list[dict]:
    """Simulate a browser who doesn't buy — may or may not enter a zone."""
    events = []

    def fmt(dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    events.append(
        build_event(
            event_type="ENTRY",
            store_id=store_id,
            camera_id="CAM_1",
            visitor_id=visitor_id,
            timestamp=fmt(entry_time),
            is_staff=False,
            confidence=round(random.uniform(0.72, 0.95), 3),
            session_seq=1,
        )
    )

    t = entry_time

    # 70% of browsers visit at least one zone
    if random.random() < 0.70:
        zone = random.choice(ZONE_POOL)
        t += timedelta(minutes=random.randint(1, 5))
        dwell = random.randint(20, 180)

        events.append(
            build_event(
                event_type="ZONE_ENTER",
                store_id=store_id,
                camera_id="CAM_2",
                visitor_id=visitor_id,
                timestamp=fmt(t),
                zone_id=zone,
                is_staff=False,
                confidence=round(random.uniform(0.70, 0.93), 3),
                session_seq=1,
            )
        )

        t += timedelta(seconds=dwell)

        events.append(
            build_event(
                event_type="ZONE_EXIT",
                store_id=store_id,
                camera_id="CAM_2",
                visitor_id=visitor_id,
                timestamp=fmt(t),
                zone_id=zone,
                dwell_ms=dwell * 1000,
                is_staff=False,
                confidence=round(random.uniform(0.70, 0.93), 3),
                session_seq=1,
            )
        )

        # 15% of browsers reach billing queue but abandon
        if random.random() < 0.15:
            t += timedelta(minutes=random.randint(2, 8))
            queue_depth = random.randint(2, 6)
            events.append(
                build_event(
                    event_type="BILLING_QUEUE_JOIN",
                    store_id=store_id,
                    camera_id="CAM_5",
                    visitor_id=visitor_id,
                    timestamp=fmt(t),
                    zone_id="CASH_COUNTER",
                    is_staff=False,
                    confidence=round(random.uniform(0.75, 0.90), 3),
                    queue_depth=queue_depth,
                    session_seq=1,
                )
            )
            t += timedelta(minutes=random.randint(1, 3))
            events.append(
                build_event(
                    event_type="BILLING_QUEUE_ABANDON",
                    store_id=store_id,
                    camera_id="CAM_5",
                    visitor_id=visitor_id,
                    timestamp=fmt(t),
                    zone_id="CASH_COUNTER",
                    is_staff=False,
                    confidence=round(random.uniform(0.75, 0.90), 3),
                    queue_depth=queue_depth,
                    session_seq=1,
                )
            )

    # EXIT
    dwell_total = random.randint(3, 20)
    exit_time = entry_time + timedelta(minutes=dwell_total)
    events.append(
        build_event(
            event_type="EXIT",
            store_id=store_id,
            camera_id="CAM_1",
            visitor_id=visitor_id,
            timestamp=fmt(exit_time),
            is_staff=False,
            confidence=round(random.uniform(0.75, 0.95), 3),
            session_seq=1,
        )
    )

    return events
