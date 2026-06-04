# PROMPT: Generate pytest tests for GET /stores/{store_id}/anomalies covering:
#   1. No anomalies for empty store (returns empty list, not 500)
#   2. BILLING_QUEUE_SPIKE triggered when queue_depth > 5 (WARN)
#   3. BILLING_QUEUE_SPIKE severity = CRITICAL when queue_depth > 8
#   4. HIGH_ABANDONMENT triggered when abandonment > 30%
#   5. DEAD_ZONE triggered when no zone events in last 30 minutes
#      (difficult to test in unit tests — mark as xfail or skip)
#   6. Response always has required fields: anomaly_id, severity, message, suggested_action
#   7. /health endpoint returns status and database fields
# CHANGES MADE: Skipped DEAD_ZONE test since it depends on real-time 'now' which
#   is hard to fake in this test setup; focused QUEUE_SPIKE on testing via ingest
#   then anomaly; added assertion that severity is one of INFO/WARN/CRITICAL.

import uuid

import pytest

from tests.conftest import CHALLENGE_DATE, make_event

QUERY_DATE = CHALLENGE_DATE


@pytest.mark.asyncio
async def test_anomalies_empty_store_no_error(client):
    """Empty store should return empty anomalies list, not 500."""
    store = f"STORE_AN_EMPTY_{uuid.uuid4().hex[:6]}"
    resp = await client.get(f"/stores/{store}/anomalies")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_anomalies" in data
    assert isinstance(data["active_anomalies"], list)
    assert "checked_at" in data


@pytest.mark.asyncio
async def test_anomalies_required_fields(client):
    """Anomaly response has required top-level fields."""
    store = f"STORE_AN_FIELDS_{uuid.uuid4().hex[:6]}"
    resp = await client.get(f"/stores/{store}/anomalies")
    assert resp.status_code == 200
    data = resp.json()
    assert "store_id" in data
    assert "active_anomalies" in data
    assert "anomaly_count" in data
    assert "checked_at" in data
    assert data["store_id"] == store


@pytest.mark.asyncio
async def test_anomaly_items_have_required_fields(client):
    """Each anomaly item must have anomaly_id, anomaly_type, severity, message, suggested_action."""
    store = f"STORE_AN_ITEM_{uuid.uuid4().hex[:6]}"

    # Trigger HIGH_ABANDONMENT by creating billing + abandon events
    vid = f"VIS_{uuid.uuid4().hex[:6]}"
    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T10:00:00Z"),
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T10:05:00Z",
            metadata={"queue_depth": 7, "session_seq": 1},
        ),
        make_event(
            "BILLING_QUEUE_ABANDON",
            visitor_id=vid,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T10:10:00Z",
        ),
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["active_anomalies"]

    for anomaly in anomalies:
        assert "anomaly_id" in anomaly
        assert "anomaly_type" in anomaly
        assert anomaly["anomaly_type"] == anomaly["anomaly_id"]
        assert "severity" in anomaly
        assert "message" in anomaly
        assert "suggested_action" in anomaly
        assert anomaly["severity"] in ("INFO", "WARN", "CRITICAL")
        assert len(anomaly["message"]) > 0


@pytest.mark.asyncio
async def test_anomaly_queue_spike_warn_at_6(client):
    """Queue depth of 6 should trigger BILLING_QUEUE_SPIKE with WARN severity."""
    store = f"STORE_QS_WARN_{uuid.uuid4().hex[:6]}"
    vid = f"VIS_{uuid.uuid4().hex[:6]}"

    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T12:00:00Z"),
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T12:30:00Z",
            metadata={"queue_depth": 6, "session_seq": 1},
        ),
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/anomalies")
    assert resp.status_code == 200

    anomalies = resp.json()["active_anomalies"]
    spike = next((a for a in anomalies if a["anomaly_id"] == "BILLING_QUEUE_SPIKE"), None)
    assert spike is not None, "Expected BILLING_QUEUE_SPIKE anomaly"
    assert spike["severity"] == "WARN"
    assert "6" in spike["message"]


@pytest.mark.asyncio
async def test_anomaly_queue_spike_critical_at_9(client):
    """Queue depth of 9 should trigger BILLING_QUEUE_SPIKE with CRITICAL severity."""
    store = f"STORE_QS_CRIT_{uuid.uuid4().hex[:6]}"
    vid = f"VIS_{uuid.uuid4().hex[:6]}"

    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T19:00:00Z"),
        make_event(
            "BILLING_QUEUE_JOIN",
            visitor_id=vid,
            store_id=store,
            zone_id="CASH_COUNTER",
            camera_id="CAM_5",
            timestamp=f"{QUERY_DATE}T19:10:00Z",
            metadata={"queue_depth": 9, "session_seq": 1},
        ),
    ]
    await client.post("/events/ingest", json=events)

    resp = await client.get(f"/stores/{store}/anomalies")
    assert resp.status_code == 200

    anomalies = resp.json()["active_anomalies"]
    spike = next((a for a in anomalies if a["anomaly_id"] == "BILLING_QUEUE_SPIKE"), None)
    assert spike is not None
    assert spike["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_anomaly_high_abandonment_triggered(client):
    """50% abandonment rate should trigger HIGH_ABANDONMENT anomaly."""
    store = f"STORE_HA_{uuid.uuid4().hex[:6]}"

    # 2 join billing queue, 1 abandons = 50% > 30% threshold
    for i, is_abandon in enumerate([True, False]):
        vid = f"VIS_ha_{i:03d}"
        base_events = [
            make_event(
                "ENTRY", visitor_id=vid, store_id=store, timestamp=f"{QUERY_DATE}T1{i}:00:00Z"
            ),
            make_event(
                "BILLING_QUEUE_JOIN",
                visitor_id=vid,
                store_id=store,
                zone_id="CASH_COUNTER",
                camera_id="CAM_5",
                timestamp=f"{QUERY_DATE}T1{i}:10:00Z",
                metadata={"queue_depth": 2, "session_seq": 1},
            ),
        ]
        if is_abandon:
            base_events.append(
                make_event(
                    "BILLING_QUEUE_ABANDON",
                    visitor_id=vid,
                    store_id=store,
                    zone_id="CASH_COUNTER",
                    camera_id="CAM_5",
                    timestamp=f"{QUERY_DATE}T1{i}:15:00Z",
                )
            )
        await client.post("/events/ingest", json=base_events)

    resp = await client.get(f"/stores/{store}/anomalies")
    assert resp.status_code == 200
    anomalies = resp.json()["active_anomalies"]
    ha = next((a for a in anomalies if a["anomaly_id"] == "HIGH_ABANDONMENT"), None)
    assert ha is not None, "Expected HIGH_ABANDONMENT anomaly at 50% rate"
    assert ha["severity"] == "WARN"


@pytest.mark.asyncio
async def test_health_endpoint_returns_healthy(client):
    """/health endpoint returns status=healthy with valid structure."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data
    assert "checked_at" in data
