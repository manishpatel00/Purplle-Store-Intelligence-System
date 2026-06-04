# PROMPT:
# Generate focused tests for pipeline/sessions.py covering:
#   1. CrossCameraDeduplicator: is_duplicate within handoff window, is_duplicate outside window
#   2. CrossCameraDeduplicator: lock, gc expired, gc with active entries
#   3. QueueDepthTracker: join increments, leave decrements to 0 (no negative), current returns 0 for unknown
#   4. flush_all_open_sessions: closes all sessions with EXIT + clip_end metadata
#   5. gc_stale_sessions: auto-closes sessions older than max_duration_seconds
# CHANGES MADE: Adapted to actual class interfaces after inspecting sessions.py source.
#   Used real CrossCameraDeduplicator and QueueDepthTracker classes.
#   flush/gc tests use a mock reid_tracker with dataclass-based sessions.

from dataclasses import dataclass
from datetime import UTC

import pytest

from pipeline.sessions import (
    CrossCameraDeduplicator,
    QueueDepthTracker,
    flush_all_open_sessions,
    gc_stale_sessions,
)

UTC = UTC


# ---------------------------------------------------------------------------
# CrossCameraDeduplicator
# ---------------------------------------------------------------------------


class TestCrossCameraDeduplicator:
    def test_not_duplicate_when_unlocked(self):
        dedup = CrossCameraDeduplicator(handoff_window_seconds=20)
        assert dedup.is_duplicate("VIS_001", "2026-04-10T10:00:00Z") is False

    def test_duplicate_within_window(self):
        dedup = CrossCameraDeduplicator(handoff_window_seconds=20)
        dedup.lock("VIS_001", "2026-04-10T10:00:00Z")
        # 10s later = within 20s window → duplicate
        assert dedup.is_duplicate("VIS_001", "2026-04-10T10:00:10Z") is True

    def test_not_duplicate_outside_window(self):
        dedup = CrossCameraDeduplicator(handoff_window_seconds=20)
        dedup.lock("VIS_001", "2026-04-10T10:00:00Z")
        # 25s later = outside 20s window → not duplicate
        assert dedup.is_duplicate("VIS_001", "2026-04-10T10:00:25Z") is False

    def test_different_visitor_not_duplicate(self):
        dedup = CrossCameraDeduplicator(handoff_window_seconds=20)
        dedup.lock("VIS_001", "2026-04-10T10:00:00Z")
        # Different visitor → not duplicate
        assert dedup.is_duplicate("VIS_002", "2026-04-10T10:00:10Z") is False

    def test_gc_removes_expired_locks(self):
        dedup = CrossCameraDeduplicator(handoff_window_seconds=20)
        dedup.lock("VIS_001", "2026-04-10T10:00:00Z")  # expires at 10:00:20
        dedup.lock("VIS_002", "2026-04-10T10:01:00Z")  # expires at 10:01:20
        # GC at 10:00:30 → VIS_001 expired, VIS_002 still active
        dedup.gc("2026-04-10T10:00:30Z")
        assert dedup.is_duplicate("VIS_001", "2026-04-10T10:00:15Z") is False  # GC'd
        assert dedup.is_duplicate("VIS_002", "2026-04-10T10:01:05Z") is True  # still locked


# ---------------------------------------------------------------------------
# QueueDepthTracker
# ---------------------------------------------------------------------------


class TestQueueDepthTracker:
    def test_join_increments_depth(self):
        qt = QueueDepthTracker()
        assert qt.join("ST1008", "CASH_COUNTER") == 1
        assert qt.join("ST1008", "CASH_COUNTER") == 2
        assert qt.join("ST1008", "CASH_COUNTER") == 3

    def test_leave_decrements_depth(self):
        qt = QueueDepthTracker()
        qt.join("ST1008", "CASH_COUNTER")
        qt.join("ST1008", "CASH_COUNTER")
        assert qt.leave("ST1008", "CASH_COUNTER") == 1

    def test_leave_does_not_go_negative(self):
        qt = QueueDepthTracker()
        assert qt.leave("ST1008", "CASH_COUNTER") == 0
        assert qt.leave("ST1008", "CASH_COUNTER") == 0

    def test_current_returns_zero_for_unknown(self):
        qt = QueueDepthTracker()
        assert qt.current("UNKNOWN_STORE", "UNKNOWN_ZONE") == 0

    def test_separate_stores_tracked_independently(self):
        qt = QueueDepthTracker()
        qt.join("STORE_A", "CASH")
        qt.join("STORE_A", "CASH")
        qt.join("STORE_B", "CASH")
        assert qt.current("STORE_A", "CASH") == 2
        assert qt.current("STORE_B", "CASH") == 1


# ---------------------------------------------------------------------------
# flush_all_open_sessions + gc_stale_sessions
# ---------------------------------------------------------------------------


@dataclass
class MockSession:
    visitor_id: str
    last_camera_id: str = "CAM_1"
    last_confidence: float = 0.9
    session_seq: int = 1
    started_at: float = 0.0


class MockReIDTracker:
    def __init__(self):
        self.active_sessions: dict[int, MockSession] = {}
        self.track_to_visitor: dict[int, str] = {}

    def add_session(self, track_id: int, session: MockSession):
        self.active_sessions[track_id] = session
        self.track_to_visitor[track_id] = session.visitor_id


@pytest.mark.asyncio
async def test_flush_closes_all_open_sessions():
    tracker = MockReIDTracker()
    tracker.add_session(1, MockSession(visitor_id="VIS_001"))
    tracker.add_session(2, MockSession(visitor_id="VIS_002"))

    events = await flush_all_open_sessions(
        store_id="ST1008",
        clip_end_ts_str="2026-04-10T10:20:00Z",
        active_sessions=list(tracker.active_sessions.items()),
        reid_tracker=tracker,
    )
    assert len(events) == 2
    assert all(e["event_type"] == "EXIT" for e in events)
    assert all(e["metadata"]["low_confidence_reason"] == "clip_end_no_exit" for e in events)
    # Tracker should be cleaned up
    assert len(tracker.active_sessions) == 0


@pytest.mark.asyncio
async def test_flush_empty_tracker_returns_nothing():
    tracker = MockReIDTracker()
    events = await flush_all_open_sessions(
        store_id="ST1008",
        clip_end_ts_str="2026-04-10T10:20:00Z",
        active_sessions=[],
        reid_tracker=tracker,
    )
    assert events == []


@pytest.mark.asyncio
async def test_gc_stale_sessions_closes_old_sessions():
    tracker = MockReIDTracker()
    # Session started 4 hours ago (14400s) — should be GC'd with 3h max
    tracker.add_session(1, MockSession(visitor_id="VIS_OLD", started_at=0.0))
    # Session started recently — should NOT be GC'd
    tracker.add_session(2, MockSession(visitor_id="VIS_NEW", started_at=14000.0))

    events = await gc_stale_sessions(
        store_id="ST1008",
        current_time_s=14400.0,
        current_ts_str="2026-04-10T14:00:00Z",
        reid_tracker=tracker,
        max_duration_seconds=10800,  # 3 hours
    )
    assert len(events) == 1
    assert events[0]["visitor_id"] == "VIS_OLD"
    assert events[0]["metadata"]["low_confidence_reason"] == "max_session_duration_exceeded"
    # VIS_NEW should still be active
    assert 2 in tracker.active_sessions
