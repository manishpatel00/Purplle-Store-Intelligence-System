# PROMPT:
# Generate tests for pipeline/emit.py covering:
#   1. build_event produces all required schema fields
#   2. build_event generates unique event_ids on each call
#   3. build_event stores queue_depth and sku_zone in metadata
#   4. compute_timestamp converts frame index to correct ISO timestamp
#   5. write_events_jsonl writes valid JSONL
#   6. append_events_jsonl appends without overwriting
#   7. build_event confidence is rounded to 4 decimal places
# CHANGES MADE: Direct tests against the real functions, no mocking needed.
#   Used tmp_path fixture for file I/O tests.

import json

from pipeline.emit import append_events_jsonl, build_event, compute_timestamp, write_events_jsonl


class TestBuildEvent:
    def test_all_required_fields_present(self):
        event = build_event(
            event_type="ENTRY",
            store_id="ST1008",
            camera_id="CAM_1",
            visitor_id="VIS_000001",
            timestamp="2026-04-10T10:00:00Z",
        )
        required_fields = {
            "event_id",
            "store_id",
            "camera_id",
            "visitor_id",
            "event_type",
            "timestamp",
            "zone_id",
            "dwell_ms",
            "is_staff",
            "confidence",
            "metadata",
        }
        assert required_fields.issubset(event.keys())

    def test_unique_event_ids(self):
        events = [
            build_event("ENTRY", "ST1008", "CAM_1", "VIS_1", "2026-04-10T10:00:00Z")
            for _ in range(100)
        ]
        ids = {e["event_id"] for e in events}
        assert len(ids) == 100  # all unique UUIDs

    def test_metadata_contains_queue_depth_and_sku_zone(self):
        event = build_event(
            event_type="BILLING_QUEUE_JOIN",
            store_id="ST1008",
            camera_id="CAM_5",
            visitor_id="VIS_1",
            timestamp="2026-04-10T10:00:00Z",
            queue_depth=3,
            sku_zone="MOISTURISER",
        )
        assert event["metadata"]["queue_depth"] == 3
        assert event["metadata"]["sku_zone"] == "MOISTURISER"

    def test_metadata_session_seq(self):
        event = build_event(
            event_type="ENTRY",
            store_id="ST1008",
            camera_id="CAM_1",
            visitor_id="VIS_1",
            timestamp="2026-04-10T10:00:00Z",
            session_seq=5,
        )
        assert event["metadata"]["session_seq"] == 5

    def test_confidence_rounded(self):
        event = build_event(
            event_type="ENTRY",
            store_id="ST1008",
            camera_id="CAM_1",
            visitor_id="VIS_1",
            timestamp="2026-04-10T10:00:00Z",
            confidence=0.123456789,
        )
        assert event["confidence"] == 0.1235  # rounded to 4 decimal places

    def test_default_values(self):
        event = build_event(
            event_type="ENTRY",
            store_id="ST1008",
            camera_id="CAM_1",
            visitor_id="VIS_1",
            timestamp="2026-04-10T10:00:00Z",
        )
        assert event["zone_id"] is None
        assert event["dwell_ms"] == 0
        assert event["is_staff"] is False
        assert event["confidence"] == 0.9

    def test_staff_flag(self):
        event = build_event(
            event_type="ENTRY",
            store_id="ST1008",
            camera_id="CAM_1",
            visitor_id="VIS_1",
            timestamp="2026-04-10T10:00:00Z",
            is_staff=True,
        )
        assert event["is_staff"] is True


class TestComputeTimestamp:
    def test_frame_zero_returns_start_time(self):
        ts = compute_timestamp("2026-04-10T10:00:00Z", frame_idx=0, fps=15.0)
        assert ts == "2026-04-10T10:00:00Z"

    def test_frame_offset(self):
        ts = compute_timestamp("2026-04-10T10:00:00Z", frame_idx=150, fps=15.0)
        # 150 frames / 15 fps = 10 seconds later
        assert ts == "2026-04-10T10:00:10Z"

    def test_fps_zero_safe(self):
        # fps=0 should not crash (uses max(fps, 1.0))
        ts = compute_timestamp("2026-04-10T10:00:00Z", frame_idx=5, fps=0.0)
        assert ts == "2026-04-10T10:00:05Z"  # treated as 1fps


class TestJSONLWriters:
    def test_write_events_jsonl(self, tmp_path):
        events = [
            build_event("ENTRY", "ST1008", "CAM_1", f"VIS_{i}", "2026-04-10T10:00:00Z")
            for i in range(3)
        ]
        path = str(tmp_path / "test_output.jsonl")
        write_events_jsonl(events, path)

        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 3
        # Each line should be valid JSON
        for line in lines:
            parsed = json.loads(line)
            assert "event_id" in parsed

    def test_write_overwrites_existing(self, tmp_path):
        path = str(tmp_path / "test_output.jsonl")
        events1 = [build_event("ENTRY", "ST1008", "CAM_1", "VIS_1", "2026-04-10T10:00:00Z")]
        events2 = [build_event("EXIT", "ST1008", "CAM_1", "VIS_2", "2026-04-10T10:05:00Z")]
        write_events_jsonl(events1, path)
        write_events_jsonl(events2, path)  # overwrites
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["event_type"] == "EXIT"

    def test_append_events_jsonl(self, tmp_path):
        path = str(tmp_path / "test_output.jsonl")
        events1 = [build_event("ENTRY", "ST1008", "CAM_1", "VIS_1", "2026-04-10T10:00:00Z")]
        events2 = [build_event("EXIT", "ST1008", "CAM_1", "VIS_2", "2026-04-10T10:05:00Z")]
        write_events_jsonl(events1, path)
        append_events_jsonl(events2, path)  # appends
        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 2
