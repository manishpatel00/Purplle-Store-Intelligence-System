# PROMPT: Generate pytest tests for GET /stores/{store_id}/metrics covering:
#   1. Empty store returns zeros for all numeric fields, no 500
#   2. Staff events (is_staff=True) are excluded from unique_visitors count
#   3. REENTRY events don't double-count toward unique_visitors
#   4. Conversion rate = 0.0 when no billing events exist
#   5. Conversion rate correctly computed when billing_visitors < total_visitors
#   6. avg_dwell_by_zone_sec is populated when ZONE_EXIT events with dwell_ms exist
#   7. abandonment_rate_pct is 100% when all billing visitors abandon
#   8. Response always has required fields even with no data
# CHANGES MADE: Added a seed helper using /events/ingest instead of direct DB writes
#   to test the full stack; moved unique_id generation into make_event conftest helper
#   to avoid UUID collisions; changed REENTRY assertion to verify count stays at 1
#   (not 2) after a REENTRY event for same visitor_id.

import uuid

import pytest

from tests.conftest import CHALLENGE_DATE, make_event, make_visitor_journey

STORE_EMPTY = f"STORE_EMPTY_{uuid.uuid4().hex[:6]}"
STORE_TEST = f"STORE_METRICS_{uuid.uuid4().hex[:6]}"
QUERY_DATE = CHALLENGE_DATE


@pytest.mark.asyncio
async def test_metrics_empty_store_returns_zeros(client):
    """Store with no events should return all zeros — never null or 500."""
    resp = await client.get(f"/stores/{STORE_EMPTY}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate_pct"] == 0.0
    assert data["abandonment_rate_pct"] == 0.0
    assert data["current_queue_depth"] == 0
    assert isinstance(data["avg_dwell_by_zone_sec"], dict)


@pytest.mark.asyncio
async def test_metrics_required_fields_present(client):
    """Response always has required fields."""
    resp = await client.get(f"/stores/{STORE_EMPTY}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    required_fields = [
        "store_id",
        "date",
        "unique_visitors",
        "conversion_rate_pct",
        "conversion_method",
        "pos_transaction_count",
        "pos_matched_visitors",
        "avg_dwell_by_zone_sec",
        "current_queue_depth",
        "abandonment_rate_pct",
        "computed_at",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


@pytest.mark.asyncio
async def test_metrics_staff_excluded_from_visitors(client):
    """Staff ENTRY events must NOT count toward unique_visitors."""
    store = f"STORE_STAFF_{uuid.uuid4().hex[:6]}"

    staff_event = make_event(
        "ENTRY",
        store_id=store,
        visitor_id="VIS_staff_01",
        is_staff=True,
        timestamp=f"{QUERY_DATE}T09:00:00Z",
    )
    visitor_event = make_event(
        "ENTRY",
        store_id=store,
        visitor_id="VIS_cust_01",
        is_staff=False,
        timestamp=f"{QUERY_DATE}T10:00:00Z",
    )

    await client.post("/events/ingest", json=[staff_event, visitor_event])

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    assert resp.json()["unique_visitors"] == 1  # only the customer


@pytest.mark.asyncio
async def test_metrics_reentry_not_double_counted(client):
    """REENTRY events for an existing visitor must not increment unique_visitors."""
    store = f"STORE_REENTRY_{uuid.uuid4().hex[:6]}"
    vid = f"VIS_{uuid.uuid4().hex[:6]}"

    entry = make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T11:00:00Z")
    reentry = make_event(
        "REENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T14:00:00Z"
    )

    await client.post("/events/ingest", json=[entry, reentry])

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    # REENTRY uses same visitor_id — unique_visitors should still be 1
    assert resp.json()["unique_visitors"] == 1


@pytest.mark.asyncio
async def test_metrics_conversion_rate_zero_without_billing(client):
    """Conversion rate should be 0.0 when no billing events exist."""
    store = f"STORE_NOBILL_{uuid.uuid4().hex[:6]}"

    events = [
        make_event("ENTRY", store_id=store, timestamp=f"{QUERY_DATE}T10:0{i}:00Z") for i in range(5)
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    assert resp.json()["conversion_rate_pct"] == 0.0


@pytest.mark.asyncio
async def test_metrics_conversion_rate_computed_correctly(client):
    """With 2 visitors and 1 buyer, conversion = 50%."""
    store = f"STORE_CONV_{uuid.uuid4().hex[:6]}"
    vid1 = f"VIS_{uuid.uuid4().hex[:6]}"
    vid2 = f"VIS_{uuid.uuid4().hex[:6]}"

    journey1 = make_visitor_journey(vid1, store_id=store, base_hour=12, is_buyer=True)
    journey2 = make_visitor_journey(vid2, store_id=store, base_hour=13, is_buyer=False)

    await client.post("/events/ingest", json=journey1 + journey2)

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unique_visitors"] == 2
    assert data["conversion_rate_pct"] == 50.0


@pytest.mark.asyncio
async def test_metrics_dwell_populated_from_zone_exit(client):
    """avg_dwell_by_zone_sec should reflect ZONE_EXIT dwell_ms values."""
    store = f"STORE_DWELL_{uuid.uuid4().hex[:6]}"
    vid = f"VIS_{uuid.uuid4().hex[:6]}"

    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T15:00:00Z"),
        make_event(
            "ZONE_ENTER",
            visitor_id=vid,
            store_id=store,
            zone_id="GOOD_VIBES",
            timestamp=f"{QUERY_DATE}T15:02:00Z",
            camera_id="CAM_2",
        ),
        make_event(
            "ZONE_EXIT",
            visitor_id=vid,
            store_id=store,
            zone_id="GOOD_VIBES",
            timestamp=f"{QUERY_DATE}T15:07:00Z",
            dwell_ms=300000,  # 300s = 5 min
            camera_id="CAM_2",
        ),
        make_event("EXIT", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T15:10:00Z"),
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    dwell = resp.json()["avg_dwell_by_zone_sec"]
    assert "GOOD_VIBES" in dwell
    assert dwell["GOOD_VIBES"] == 300.0  # 300,000ms / 1000


@pytest.mark.asyncio
async def test_metrics_abandonment_100_percent(client):
    """100% abandonment when every billing joiner also abandons."""
    store = f"STORE_ABANDON_{uuid.uuid4().hex[:6]}"
    vid = f"VIS_{uuid.uuid4().hex[:6]}"

    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T16:00:00Z"),
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T16:10:00Z",
            metadata={"queue_depth": 5, "session_seq": 1},
        ),
        make_event(
            "BILLING_QUEUE_ABANDON",
            visitor_id=vid,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T16:15:00Z",
        ),
        make_event("EXIT", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T16:16:00Z"),
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    assert resp.json()["abandonment_rate_pct"] == 100.0


@pytest.mark.asyncio
async def test_metrics_pos_correlated_conversion(client, monkeypatch, tmp_path):
    """POS conversion: billing join within 5 min before transaction counts as converted."""
    store = f"STORE_POS_{uuid.uuid4().hex[:6]}"
    csv = tmp_path / "pos.csv"
    csv.write_text(
        "order_id,order_date,order_time,store_id,product_id,brand_name,total_amount\n"
        f"9001,10-04-2026,12:42:00,{store},1,Brand,100\n"
        f"9002,10-04-2026,14:00:00,{store},2,Brand,200\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POS_CSV_PATH", str(csv))
    vid_match = "VIS_POS_MATCH"
    vid_no = "VIS_POS_NO"

    events = [
        make_event(
            "ENTRY", visitor_id=vid_match, store_id=store, timestamp=f"{QUERY_DATE}T12:00:00Z"
        ),
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid_match,
            store_id=store,
            camera_id="CAM_5",
            zone_id="CASH_COUNTER",
            timestamp=f"{QUERY_DATE}T12:41:00Z",
        ),
        make_event("ENTRY", visitor_id=vid_no, store_id=store, timestamp=f"{QUERY_DATE}T12:05:00Z"),
        make_event("EXIT", visitor_id=vid_no, store_id=store, timestamp=f"{QUERY_DATE}T12:30:00Z"),
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/metrics?target_date={QUERY_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["conversion_method"] == "pos_correlated"
    assert data["pos_transaction_count"] == 2
    assert data["pos_matched_visitors"] == 1
    assert data["unique_visitors"] == 2
    assert data["conversion_rate_pct"] == 50.0
