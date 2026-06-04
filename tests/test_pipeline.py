# PROMPT: Generate pytest tests for POST /events/ingest covering:
#   1. Valid single event ingest returns accepted=1
#   2. Idempotent ingest: same event_id posted twice -> duplicates=1 on second call
#   3. Invalid event_type returns rejected with reason
#   4. Staff events are accepted (is_staff=True is valid)
#   5. Batch ingest of 5 events all accepted
#   6. Batch > 500 events returns 400
#   7. Invalid timestamp format returns rejected (not 500)
#   8. Empty batch returns accepted=0
# CHANGES MADE: Used make_event() from conftest instead of inline dicts to reduce
#   boilerplate; clarified assertion on rejected to check 'reason' key exists;
#   added test_batch_over_limit to use list comprehension for 501 events (cleaner).

import pytest

from tests.conftest import CHALLENGE_DATE, make_event


@pytest.mark.asyncio
async def test_ingest_single_valid_event(client):
    """Single valid ENTRY event should be accepted."""
    event = make_event("ENTRY")
    resp = await client.post("/events/ingest", json=[event])
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 1
    assert data["total_received"] == 1
    assert data["rejected"] == []


@pytest.mark.asyncio
async def test_ingest_idempotent(client):
    """Posting same event_id twice must not create duplicates."""
    event = make_event("ENTRY")

    r1 = await client.post("/events/ingest", json=[event])
    assert r1.json()["accepted"] == 1

    r2 = await client.post("/events/ingest", json=[event])
    data2 = r2.json()
    assert data2["accepted"] == 0
    assert data2["duplicates"] == 1


@pytest.mark.asyncio
async def test_ingest_invalid_event_type(client):
    """Unknown event_type should be rejected with a descriptive reason."""
    event = make_event("TELEPORT")  # not a real event type
    resp = await client.post("/events/ingest", json=[event])
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert len(data["detail"]) == 1
    assert "reason" in data["detail"][0]
    assert "event_type" in data["detail"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_ingest_staff_event_accepted(client):
    """Staff ENTRY events (is_staff=True) should be accepted, not rejected."""
    event = make_event("ENTRY", is_staff=True, visitor_id="VIS_staff001")
    resp = await client.post("/events/ingest", json=[event])
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1


@pytest.mark.asyncio
async def test_ingest_batch_of_five(client):
    """Batch of 5 unique events should all be accepted."""
    events = [make_event("ENTRY", timestamp=f"{CHALLENGE_DATE}T1{i}:00:00Z") for i in range(5)]
    resp = await client.post("/events/ingest", json=events)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 5
    assert data["total_received"] == 5
    assert data["rejected"] == []


@pytest.mark.asyncio
async def test_ingest_batch_over_limit(client):
    """Batch > 500 events should return HTTP 400."""
    events = [make_event("ENTRY") for _ in range(501)]
    resp = await client.post("/events/ingest", json=events)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_ingest_invalid_timestamp(client):
    """Malformed timestamp should be rejected, not cause a 500."""
    event = make_event("ENTRY", timestamp="not-a-timestamp")
    resp = await client.post("/events/ingest", json=[event])
    assert resp.status_code == 400
    data = resp.json()
    assert "detail" in data
    assert len(data["detail"]) == 1
    assert "timestamp" in data["detail"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_ingest_empty_batch(client):
    """Empty batch should return accepted=0 without errors."""
    resp = await client.post("/events/ingest", json=[])
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 0
    assert data["total_received"] == 0


@pytest.mark.asyncio
async def test_ingest_all_valid_event_types(client):
    """All 8 valid event types should be accepted."""
    valid_types = [
        "ENTRY",
        "EXIT",
        "REENTRY",
        "ZONE_ENTER",
        "ZONE_EXIT",
        "ZONE_DWELL",
        "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON",
    ]
    events = [
        make_event(etype, zone_id="FACES_CANADA" if "ZONE" in etype or "BILLING" in etype else None)
        for etype in valid_types
    ]
    resp = await client.post("/events/ingest", json=events)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] == 8
    assert data["rejected"] == []
