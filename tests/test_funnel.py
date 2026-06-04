# PROMPT: Generate pytest tests for GET /stores/{store_id}/funnel covering:
#   1. Empty store returns 4-stage funnel with all zeros
#   2. Funnel stages are in order: entry, zone_visit, billing_queue, purchase
#   3. Dropoff pct at entry stage is always 0.0
#   4. Correct dropoff when zone visitors < entry visitors
#   5. Purchase count = billing_count - abandon_count (not billing_count)
#   6. overall_conversion_rate_pct matches purchase/entry ratio
#   7. All required fields present per stage
# CHANGES MADE: Used make_visitor_journey() for full journeys; separated buyer/browser
#   counts to verify each funnel stage independently; added assertion that
#   stage labels are strings (not null).

import uuid

import pytest

from tests.conftest import CHALLENGE_DATE, make_event, make_visitor_journey

QUERY_DATE = CHALLENGE_DATE


@pytest.mark.asyncio
async def test_funnel_empty_store_returns_zeros(client):
    """Empty store funnel should have 4 stages all at zero."""
    store = f"STORE_F_EMPTY_{uuid.uuid4().hex[:6]}"
    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    assert "funnel" in data
    assert len(data["funnel"]) == 4
    for stage in data["funnel"]:
        assert stage["count"] == 0


@pytest.mark.asyncio
async def test_funnel_required_fields_per_stage(client):
    """Each funnel stage must have: stage, label, count, dropoff_pct."""
    store = f"STORE_F_FIELDS_{uuid.uuid4().hex[:6]}"
    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    for stage in resp.json()["funnel"]:
        assert "stage" in stage
        assert "label" in stage
        assert "count" in stage
        assert "dropoff_pct" in stage
        assert isinstance(stage["label"], str)
        assert len(stage["label"]) > 0


@pytest.mark.asyncio
async def test_funnel_entry_dropoff_is_zero(client):
    """Entry stage dropoff_pct must always be 0.0."""
    store = f"STORE_F_ENTRY_{uuid.uuid4().hex[:6]}"
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T10:00:00Z")
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    entry_stage = resp.json()["funnel"][0]
    assert entry_stage["stage"] == "entry"
    assert entry_stage["dropoff_pct"] == 0.0
    assert entry_stage["count"] == 1


@pytest.mark.asyncio
async def test_funnel_stage_order(client):
    """Stages must be: entry, zone_visit, billing_queue, purchase — in that order."""
    store = f"STORE_F_ORDER_{uuid.uuid4().hex[:6]}"
    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    stages = [s["stage"] for s in resp.json()["funnel"]]
    assert stages == ["entry", "zone_visit", "billing_queue", "purchase"]


@pytest.mark.asyncio
async def test_funnel_dropoff_when_not_all_zone_visit(client):
    """10 visitors, only 6 visit zones -> zone_visit dropoff = 40%."""
    store = f"STORE_F_DROP_{uuid.uuid4().hex[:6]}"
    events = []

    # 10 enter
    for i in range(10):
        vid = f"VIS_f_{i:03d}"
        events.append(
            make_event(
                "ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T10:{i:02d}:00Z"
            )
        )

    # 6 visit a zone
    for i in range(6):
        vid = f"VIS_f_{i:03d}"
        events.append(
            make_event(
                "ZONE_ENTER",
                visitor_id=vid,
                store_id=store,
                zone_id="FACES_CANADA",
                camera_id="CAM_2",
                timestamp=f"{QUERY_DATE}T10:{i:02d}:05Z",
            )
        )

    await client.post("/events/ingest", json=events)
    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    funnel = resp.json()["funnel"]

    entry_stage = next(s for s in funnel if s["stage"] == "entry")
    zone_stage = next(s for s in funnel if s["stage"] == "zone_visit")

    assert entry_stage["count"] == 10
    assert zone_stage["count"] == 6
    assert zone_stage["dropoff_pct"] == 40.0


@pytest.mark.asyncio
async def test_funnel_purchase_excludes_abandoners(client):
    """Purchase = billing_queue_join - abandonment. Abandoners must not count."""
    store = f"STORE_F_PURCH_{uuid.uuid4().hex[:6]}"

    # Buyer 1: joins + does NOT abandon
    vid_buyer = f"VIS_{uuid.uuid4().hex[:6]}"
    journey_buyer = make_visitor_journey(vid_buyer, store_id=store, base_hour=12, is_buyer=True)

    # Browser: joins + abandons
    vid_abandon = f"VIS_{uuid.uuid4().hex[:6]}"
    events_abandon = [
        make_event(
            "ENTRY", visitor_id=vid_abandon, store_id=store, timestamp=f"{QUERY_DATE}T13:00:00Z"
        ),
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid_abandon,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T13:10:00Z",
            metadata={"queue_depth": 4, "session_seq": 1},
        ),
        make_event(
            "BILLING_QUEUE_ABANDON",
            visitor_id=vid_abandon,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T13:15:00Z",
        ),
        make_event(
            "EXIT", visitor_id=vid_abandon, store_id=store, timestamp=f"{QUERY_DATE}T13:20:00Z"
        ),
    ]

    await client.post("/events/ingest", json=journey_buyer + events_abandon)
    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    assert resp.status_code == 200

    funnel = resp.json()["funnel"]
    billing = next(s for s in funnel if s["stage"] == "billing_queue")
    purchase = next(s for s in funnel if s["stage"] == "purchase")

    assert billing["count"] == 2  # both joined
    assert purchase["count"] == 1  # only 1 completed (no abandon)


@pytest.mark.asyncio
async def test_funnel_overall_conversion_rate(client):
    """overall_conversion_rate_pct = purchase_count / entry_count * 100."""
    store = f"STORE_F_CONV_{uuid.uuid4().hex[:6]}"

    # 4 visitors, 1 buyer
    events = []
    for i in range(4):
        vid = f"VIS_{uuid.uuid4().hex[:6]}"
        events.append(
            make_event(
                "ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T1{i}:00:00Z"
            )
        )

    vid_buyer = f"VIS_{uuid.uuid4().hex[:6]}"
    events.append(
        make_event(
            "ENTRY", visitor_id=vid_buyer, store_id=store, timestamp=f"{QUERY_DATE}T14:30:00Z"
        )
    )
    events.append(
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid_buyer,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T14:45:00Z",
            metadata={"queue_depth": 1, "session_seq": 1},
        )
    )

    await client.post("/events/ingest", json=events)
    resp = await client.get(f"/stores/{store}/funnel?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    # 1 buyer out of 5 total = 20%
    assert data["overall_conversion_rate_pct"] == 20.0
