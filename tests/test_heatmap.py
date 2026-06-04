# PROMPT: Generate pytest tests for GET /stores/{store_id}/heatmap covering:
#   1. Empty store returns all configured zones with visits=0 and intensity=0
#   2. Zones with visits get normalized intensity 0-100
#   3. data_confidence LOW when fewer than 20 ENTRY sessions
#   4. Staff ZONE_ENTER events excluded from visit counts
# CHANGES MADE: Added explicit check that FACES_CANADA appears with visits=0 on empty
#   ingest; used make_visitor_journey for HIGH confidence path with 25 visitors.

import pytest

from tests.conftest import CHALLENGE_DATE, STORE_ID, make_event, make_visitor_journey


@pytest.mark.asyncio
async def test_heatmap_empty_store_includes_zero_zones(client):
    resp = await client.get(f"/stores/{STORE_ID}/heatmap?target_date={CHALLENGE_DATE}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["data_confidence"] == "LOW"
    assert data["session_count"] == 0
    zone_ids = {z["zone_id"] for z in data["zones"]}
    assert "FACES_CANADA" in zone_ids
    faces = next(z for z in data["zones"] if z["zone_id"] == "FACES_CANADA")
    assert faces["visits"] == 0
    assert faces["intensity"] == 0
    assert faces["avg_dwell_ms"] == 0


@pytest.mark.asyncio
async def test_heatmap_intensity_normalized(client):
    events = []
    for i in range(3):
        vid = f"VIS_HM_{i}"
        events.extend(make_visitor_journey(vid, base_hour=10 + i, is_buyer=False))
    # Extra visits to FACES_CANADA only for first visitor
    events.append(
        make_event(
            "ZONE_ENTER",
            visitor_id="VIS_HM_0",
            zone_id="FACES_CANADA",
            camera_id="CAM_2",
            timestamp=f"{CHALLENGE_DATE}T10:20:00Z",
        )
    )
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{STORE_ID}/heatmap?target_date={CHALLENGE_DATE}")
    data = resp.json()
    faces = next(z for z in data["zones"] if z["zone_id"] == "FACES_CANADA")
    assert faces["visits"] >= 1
    assert 0 <= faces["intensity"] <= 100
    max_intensity = max(z["intensity"] for z in data["zones"])
    assert max_intensity == 100


@pytest.mark.asyncio
async def test_heatmap_excludes_staff(client):
    staff = make_event(
        "ZONE_ENTER",
        visitor_id="VIS_STAFF_HM",
        zone_id="GOOD_VIBES",
        is_staff=True,
        timestamp=f"{CHALLENGE_DATE}T11:00:00Z",
    )
    visitor = make_event(
        "ENTRY",
        visitor_id="VIS_CUST_HM",
        timestamp=f"{CHALLENGE_DATE}T11:01:00Z",
    )
    visitor_zone = make_event(
        "ZONE_ENTER",
        visitor_id="VIS_CUST_HM",
        zone_id="GOOD_VIBES",
        camera_id="CAM_2",
        timestamp=f"{CHALLENGE_DATE}T11:02:00Z",
    )
    await client.post("/events/ingest", json=[staff, visitor, visitor_zone])

    resp = await client.get(f"/stores/{STORE_ID}/heatmap?target_date={CHALLENGE_DATE}")
    good = next(z for z in resp.json()["zones"] if z["zone_id"] == "GOOD_VIBES")
    assert good["visits"] == 1


@pytest.mark.asyncio
async def test_heatmap_high_confidence_with_enough_sessions(client):
    events = []
    for i in range(20):
        events.extend(make_visitor_journey(f"VIS_HC_{i}", base_hour=12, is_buyer=False))
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{STORE_ID}/heatmap?target_date={CHALLENGE_DATE}")
    data = resp.json()
    assert data["data_confidence"] == "HIGH"
    assert data["session_count"] >= 20
