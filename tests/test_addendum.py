# PROMPT: Generate pytest tests for addendum features covering:
#   1. POS multi-day receipt deduplication in _load_pos_data
#   2. Clip-end flushing via flush_all_open_sessions
#   3. Re-entry deduplication within the reentry window
#   4. CONVERSION_DROP anomaly detection comparing today's rate vs 7-day trailing average
# CHANGES MADE: Added four test cases targeting these specific pipeline and API additions.

import os

import pytest

from pipeline.sessions import flush_all_open_sessions
from pipeline.synthetic_events import _load_pos_data
from pipeline.tracker import ReIDTracker
from tests.conftest import make_event


def test_pos_receipt_deduplication():
    """Verify that _load_pos_data correctly deduplicates items with the same order_id."""
    csv_path = os.path.join("tests", "fixtures", "pos_sample.csv")
    orders = _load_pos_data(csv_path)
    # The fixture CSV has 10 lines, but only 3 unique order IDs (1, 2, and 3)
    assert len(orders) == 3
    order_ids = {o["order_id"] for o in orders}
    assert order_ids == {"1", "2", "3"}


@pytest.mark.asyncio
async def test_clip_end_flushing():
    """Verify flush_all_open_sessions generates exits for all active sessions and clears ReIDTracker."""

    class DummySession:
        def __init__(self, visitor_id, camera_id, confidence, seq, started_at):
            self.visitor_id = visitor_id
            self.last_camera_id = camera_id
            self.last_confidence = confidence
            self.session_seq = seq
            self.started_at = started_at

    reid_tracker = ReIDTracker()
    reid_tracker.active_sessions = {
        "track_01": DummySession("VIS_01", "CAM_1", 0.95, 1, 100.0),
        "track_02": DummySession("VIS_02", "CAM_2", 0.88, 1, 105.0),
    }
    reid_tracker.track_to_visitor = {"track_01": "VIS_01", "track_02": "VIS_02"}

    events = await flush_all_open_sessions(
        store_id="STORE_BLR_002",
        clip_end_ts_str="2026-04-10T10:10:00Z",
        active_sessions=[],
        reid_tracker=reid_tracker,
    )

    # It should emit EXIT events for all open sessions
    assert len(events) == 2
    assert all(e["event_type"] == "EXIT" for e in events)
    assert events[0]["visitor_id"] == "VIS_01"
    assert events[1]["visitor_id"] == "VIS_02"

    # Reid tracker active sessions should be cleared
    assert len(reid_tracker.active_sessions) == 0
    assert len(reid_tracker.track_to_visitor) == 0


@pytest.mark.asyncio
async def test_reentry_deduplication(client):
    """Verify that a reentry event within 15 minutes is associated with the same session/visitor."""
    store = "STORE_REENTRY_TEST"
    vid = "VIS_reentry_01"

    events = [
        make_event("ENTRY", visitor_id=vid, store_id=store, timestamp="2026-04-10T10:00:00Z"),
        make_event("EXIT", visitor_id=vid, store_id=store, timestamp="2026-04-10T10:05:00Z"),
        make_event("REENTRY", visitor_id=vid, store_id=store, timestamp="2026-04-10T10:10:00Z"),
    ]
    resp = await client.post("/events/ingest", json=events)
    assert resp.status_code == 200

    # Query metrics and check that unique_visitors count is 1 (reentry does not double count)
    m_resp = await client.get(f"/stores/{store}/metrics?target_date=2026-04-10")
    assert m_resp.status_code == 200
    assert m_resp.json()["unique_visitors"] == 1


@pytest.mark.asyncio
async def test_conversion_drop_anomaly(client):
    """Verify that CONVERSION_DROP is triggered when today's conversion drops below 80% of the 7-day average."""
    store = "STORE_CONV_DROP_TEST"
    events = []

    # Historical data (3 days ago): 10 visitors, 5 buyers = 50% conversion rate
    for i in range(10):
        vid = f"VIS_hist_{i}"
        is_buyer = i < 5
        events.append(
            make_event("ENTRY", visitor_id=vid, store_id=store, timestamp="2026-04-07T12:00:00Z")
        )
        if is_buyer:
            events.append(
                make_event(
                    "BILLING_QUEUE_JOIN",
                    visitor_id=vid,
                    store_id=store,
                    zone_id="CASH_COUNTER",
                    camera_id="CAM_5",
                    timestamp="2026-04-07T12:10:00Z",
                )
            )

    # Today's data (2026-04-10): 10 visitors, 0 buyers = 0% conversion rate
    for i in range(10):
        vid = f"VIS_today_{i}"
        events.append(
            make_event("ENTRY", visitor_id=vid, store_id=store, timestamp="2026-04-10T12:00:00Z")
        )

    # Ingest all events
    resp = await client.post("/events/ingest", json=events)
    assert resp.status_code == 200

    # Query anomalies today
    a_resp = await client.get(f"/stores/{store}/anomalies")
    assert a_resp.status_code == 200
    data = a_resp.json()
    anomalies = data["active_anomalies"]

    # Assert CONVERSION_DROP is present
    conv_drop = next((a for a in anomalies if a["anomaly_id"] == "CONVERSION_DROP"), None)
    assert conv_drop is not None, "Expected CONVERSION_DROP anomaly to be triggered"
    assert conv_drop["today_rate"] == 0.0
    assert conv_drop["trailing_rate"] == 50.0
