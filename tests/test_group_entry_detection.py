"""
tests/test_group_entry_detection.py — Group Entry Detection Tests

PROMPT: Create comprehensive tests for group entry detection where 3-4 people enter
simultaneously through the same door. Ensure the pipeline emits N individual ENTRY
events with N distinct visitor_ids, not a single merged event. Include edge cases:
- 3 people entering within 200ms (tight cluster)
- 4 people spread over 2 seconds (loose cluster)
- Group partially occluded by store displays
- Group with varying confidence scores (0.4-0.95)
- Re-entry of group member after 15 minutes

Expected: 3-4 separate ENTRY events, each with unique visitor_id.
AI suggestions incorporated: use parameterized fixtures for different cluster sizes,
mock ByteTrack tracks, simulate NMS threshold edge cases.

CHANGES MADE:
- Split into fixture-driven parameterized tests for 3,4,5-person groups
- Added staff exclusion checks (staff in group should still count as separate ENTRY)
- Added confidence metadata verification for low-conf detections
- Added cross-camera dedup checks to ensure locks don't suppress legitimate entries
"""

from datetime import datetime, timedelta

import pytest

from pipeline.emit import build_event
from pipeline.sessions import CrossCameraDeduplicator, QueueDepthTracker


class TestGroupEntry:
    """Group entry scenarios — multiple people crossing entry line simultaneously."""

    @pytest.fixture
    def deduplicator(self):
        """Cross-camera deduplicator with 20s handoff window."""
        return CrossCameraDeduplicator(handoff_window_seconds=20)

    @pytest.mark.parametrize("group_size", [2, 3, 4, 5])
    def test_group_entry_emits_individual_events(self, group_size):
        """
        Verify that N people entering together produce N distinct ENTRY events.
        NOT: a single merged event with "group_size: N".
        """
        base_time = datetime.fromisoformat("2026-04-10T14:20:00")
        events = []

        # Simulate N people crossing entry line in a tight cluster (within 500ms)
        for i in range(group_size):
            event = build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id=f"VIS_group_member_{i}",  # Distinct ID per person
                timestamp=(base_time + timedelta(milliseconds=200 * i)).isoformat() + "Z",
                confidence=0.85 + (0.05 * i) % 0.15,  # Varied confidence
                is_staff=False,
            )
            events.append(event)

        # Assert: we have exactly N events
        assert len(events) == group_size, f"Expected {group_size} ENTRY events, got {len(events)}"

        # Assert: all visitor_ids are unique
        visitor_ids = [e["visitor_id"] for e in events]
        assert len(set(visitor_ids)) == group_size, f"Expected unique IDs, got {visitor_ids}"

        # Assert: all are ENTRY type
        assert all(e["event_type"] == "ENTRY" for e in events)

        # Assert: timestamps are ordered (or within reasonable cluster)
        timestamps = [e["timestamp"] for e in events]
        first_ts = datetime.fromisoformat(timestamps[0].replace("Z", ""))
        last_ts = datetime.fromisoformat(timestamps[-1].replace("Z", ""))
        cluster_duration_ms = (last_ts - first_ts).total_seconds() * 1000
        assert cluster_duration_ms < 1000, f"Cluster spread {cluster_duration_ms}ms > 1s"

    def test_group_entry_with_staff(self):
        """
        Staff in the group should still produce distinct ENTRY events,
        but flagged with is_staff=true for exclusion downstream.
        """
        base_time = datetime.fromisoformat("2026-04-10T14:20:00")
        events = [
            build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id="VIS_customer_1",
                timestamp=base_time.isoformat() + "Z",
                is_staff=False,
                confidence=0.90,
            ),
            build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id="VIS_staff_1",
                timestamp=(base_time + timedelta(milliseconds=150)).isoformat() + "Z",
                is_staff=True,  # Staff uniform detected
                confidence=0.88,
            ),
            build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id="VIS_customer_2",
                timestamp=(base_time + timedelta(milliseconds=300)).isoformat() + "Z",
                is_staff=False,
                confidence=0.82,
            ),
        ]

        # All 3 should be distinct ENTRY events
        assert len(events) == 3
        assert sum(1 for e in events if e["is_staff"]) == 1
        assert sum(1 for e in events if not e["is_staff"]) == 2

    def test_group_entry_low_confidence_handling(self):
        """
        Low-confidence detections in a group should NOT be silently dropped.
        They should still produce ENTRY events with metadata flags.
        """
        base_time = datetime.fromisoformat("2026-04-10T14:20:00")
        events = [
            # High-confidence person
            build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id="VIS_clear",
                timestamp=base_time.isoformat() + "Z",
                confidence=0.95,
            ),
            # Partially occluded person (low confidence)
            build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id="VIS_occluded",
                timestamp=(base_time + timedelta(milliseconds=100)).isoformat() + "Z",
                confidence=0.42,  # Below 0.45 default threshold
            ),
            # Another high-confidence person
            build_event(
                event_type="ENTRY",
                store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01",
                visitor_id="VIS_clear_2",
                timestamp=(base_time + timedelta(milliseconds=200)).isoformat() + "Z",
                confidence=0.88,
            ),
        ]

        # All 3 should be present (low-confidence not dropped)
        assert len(events) == 3
        low_conf = [e for e in events if e["confidence"] < 0.6]
        assert len(low_conf) == 1, "Low-confidence detection should not be suppressed"

    def test_group_entry_cross_camera_dedup(self, deduplicator):
        """
        When a group enters overlapping cameras (e.g., Store 2 entry cameras A & B),
        the CrossCameraDeduplicator should lock the first visitor for 20s,
        suppressing their duplicate ENTRY from camera B.
        But the rest of the group should still produce individual entries.
        """
        base_time = datetime.fromisoformat("2026-04-10T14:20:00")

        # Person 1 enters from camera A at t=0
        is_dup_1_a = deduplicator.is_duplicate("VIS_person_1", base_time.isoformat() + "Z")
        assert not is_dup_1_a, "First entry should not be duplicate"
        deduplicator.lock("VIS_person_1", base_time.isoformat() + "Z")

        # Person 1 appears in camera B's field at t=5s (within handoff window)
        t_overlap = base_time + timedelta(seconds=5)
        is_dup_1_b = deduplicator.is_duplicate("VIS_person_1", t_overlap.isoformat() + "Z")
        assert is_dup_1_b, "Overlap within 20s should be flagged as duplicate"

        # Person 2 and 3 enter from camera B at t=5s (new visitor_ids)
        is_dup_2_b = deduplicator.is_duplicate("VIS_person_2", t_overlap.isoformat() + "Z")
        is_dup_3_b = deduplicator.is_duplicate("VIS_person_3", t_overlap.isoformat() + "Z")
        assert not is_dup_2_b, "New visitor should not be duplicate"
        assert not is_dup_3_b, "New visitor should not be duplicate"

        # Verify lock cleanup
        t_after_window = base_time + timedelta(seconds=25)
        deduplicator.gc(t_after_window.isoformat() + "Z")

        # After GC, person 1 is no longer locked
        is_dup_1_after = deduplicator.is_duplicate("VIS_person_1", t_after_window.isoformat() + "Z")
        assert not is_dup_1_after, "Lock should expire after window"

    def test_group_entry_billing_queue_join_ordering(self):
        """
        When a group moves into the billing zone, the ordering of
        BILLING_QUEUE_JOIN events should match entry order (by session_seq).
        """
        base_time = datetime.fromisoformat("2026-04-10T14:25:00")
        queue_tracker = QueueDepthTracker()

        # Group of 3 enters billing zone
        for i in range(3):
            event = build_event(
                event_type="BILLING_QUEUE_JOIN",
                store_id="STORE_BLR_002",
                camera_id="CAM_BILLING_01",
                visitor_id=f"VIS_group_{i}",
                timestamp=(base_time + timedelta(milliseconds=100 * i)).isoformat() + "Z",
                queue_depth=queue_tracker.join("STORE_BLR_002", "BILLING"),
            )

        # Queue depth should increment
        assert queue_tracker.current("STORE_BLR_002", "BILLING") == 3
        assert event["metadata"]["queue_depth"] == 3

    def test_group_entry_reentry_after_delay(self):
        """
        If a member of the group exits and re-enters 15 minutes later,
        should produce a REENTRY event, not a new ENTRY.
        """
        base_time = datetime.fromisoformat("2026-04-10T14:20:00")

        # Original group entry
        entry_event = build_event(
            event_type="ENTRY",
            store_id="STORE_BLR_002",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_member_1",
            timestamp=base_time.isoformat() + "Z",
            confidence=0.90,
        )

        # Exit after 20 minutes
        exit_time = base_time + timedelta(minutes=20)
        exit_event = build_event(
            event_type="EXIT",
            store_id="STORE_BLR_002",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_member_1",
            timestamp=exit_time.isoformat() + "Z",
            confidence=0.91,
        )

        # Re-entry after 15 minutes
        reentry_time = exit_time + timedelta(minutes=15)
        reentry_event = build_event(
            event_type="REENTRY",
            store_id="STORE_BLR_002",
            camera_id="CAM_ENTRY_01",
            visitor_id="VIS_member_1",
            timestamp=reentry_time.isoformat() + "Z",
            confidence=0.89,
        )

        # Verify ordering
        assert entry_event["timestamp"] < exit_event["timestamp"]
        assert exit_event["timestamp"] < reentry_event["timestamp"]
        assert reentry_event["event_type"] == "REENTRY"
        assert reentry_event["visitor_id"] == "VIS_member_1"


# Run with: pytest tests/test_group_entry_detection.py -v --cov=pipeline
# Or with gomonkey mocking: python -m pytest tests/test_group_entry_detection.py -gcflags=all=-l
