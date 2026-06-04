# PROMPT:
# Generate tests for pipeline/tracker.py (ReIDTracker) covering:
#   1. on_entry creates a new visitor session with unique visitor_id
#   2. Group entry: N people produce N distinct visitor_ids
#   3. Re-entry within window with matching embedding produces REENTRY (same visitor_id)
#   4. Re-entry outside window produces new ENTRY (different visitor_id)
#   5. on_exit moves session from active to exited
#   6. get_visitor_id returns correct visitor_id for known track_id
#   7. get_session_seq returns 1 for new visitor, increments on re-entry
#   8. _find_reentry_match returns None when no embedding provided
# CHANGES MADE: Used real ReIDTracker class. Created synthetic embeddings
#   for cosine similarity matching. Avoided ByteTrack dependency entirely.

import numpy as np

from pipeline.tracker import ReIDTracker


class TestReIDTrackerEntry:
    def test_first_entry_creates_visitor(self):
        tracker = ReIDTracker()
        emb = np.random.rand(256).astype(np.float32)
        vid, is_reentry = tracker.on_entry(track_id=1, embedding=emb, frame_time_s=0.0)
        assert vid.startswith("VIS_")
        assert is_reentry is False
        assert tracker.get_visitor_id(1) == vid

    def test_group_entry_produces_distinct_visitor_ids(self):
        tracker = ReIDTracker()
        visitor_ids = set()
        for i in range(4):
            emb = np.random.rand(256).astype(np.float32)
            vid, is_reentry = tracker.on_entry(track_id=i + 1, embedding=emb, frame_time_s=0.0)
            visitor_ids.add(vid)
            assert is_reentry is False
        assert len(visitor_ids) == 4  # all distinct

    def test_entry_with_no_embedding(self):
        tracker = ReIDTracker()
        vid, is_reentry = tracker.on_entry(track_id=1, embedding=None, frame_time_s=0.0)
        assert vid.startswith("VIS_")
        assert is_reentry is False


class TestReIDTrackerReentry:
    def test_reentry_within_window_same_visitor(self):
        tracker = ReIDTracker()
        emb = np.array([1.0, 0.0, 0.0] * 85 + [1.0], dtype=np.float32)  # 256-d

        vid1, _ = tracker.on_entry(track_id=1, embedding=emb, frame_time_s=0.0)
        tracker.on_exit(track_id=1, timestamp_s=60.0)

        # Same embedding, within 300s window
        vid2, is_reentry = tracker.on_entry(track_id=2, embedding=emb, frame_time_s=120.0)
        assert is_reentry is True
        assert vid2 == vid1  # same visitor

    def test_reentry_outside_window_new_visitor(self):
        tracker = ReIDTracker()
        emb = np.array([1.0, 0.0, 0.0] * 85 + [1.0], dtype=np.float32)

        vid1, _ = tracker.on_entry(track_id=1, embedding=emb, frame_time_s=0.0)
        tracker.on_exit(track_id=1, timestamp_s=60.0)

        # Same embedding but 600s later → outside 300s window → new visitor
        vid2, is_reentry = tracker.on_entry(track_id=2, embedding=emb, frame_time_s=660.0)
        assert is_reentry is False
        assert vid2 != vid1  # new visitor

    def test_reentry_with_different_embedding_no_match(self):
        tracker = ReIDTracker()
        emb1 = np.array([1.0, 0.0] * 128, dtype=np.float32)  # 256-d
        emb2 = np.array([0.0, 1.0] * 128, dtype=np.float32)  # orthogonal

        vid1, _ = tracker.on_entry(track_id=1, embedding=emb1, frame_time_s=0.0)
        tracker.on_exit(track_id=1, timestamp_s=60.0)

        vid2, is_reentry = tracker.on_entry(track_id=2, embedding=emb2, frame_time_s=120.0)
        assert is_reentry is False  # embeddings too different
        assert vid2 != vid1


class TestReIDTrackerExit:
    def test_on_exit_moves_session_to_exited(self):
        tracker = ReIDTracker()
        emb = np.random.rand(256).astype(np.float32)
        vid, _ = tracker.on_entry(track_id=1, embedding=emb, frame_time_s=0.0)
        assert 1 in tracker.active_sessions
        tracker.on_exit(track_id=1, timestamp_s=60.0)
        assert 1 not in tracker.active_sessions
        assert len(tracker.exited_sessions) == 1
        assert tracker.exited_sessions[0].visitor_id == vid

    def test_exit_unknown_track_no_error(self):
        tracker = ReIDTracker()
        tracker.on_exit(track_id=999, timestamp_s=60.0)  # should not raise


class TestReIDTrackerHelpers:
    def test_get_visitor_id_unknown_returns_none(self):
        tracker = ReIDTracker()
        assert tracker.get_visitor_id(999) is None

    def test_get_session_seq_new_visitor(self):
        tracker = ReIDTracker()
        emb = np.random.rand(256).astype(np.float32)
        vid, _ = tracker.on_entry(track_id=1, embedding=emb, frame_time_s=0.0)
        assert tracker.get_session_seq(vid) == 1

    def test_get_session_seq_increments_on_reentry(self):
        tracker = ReIDTracker()
        emb = np.array([1.0, 0.0, 0.0] * 85 + [1.0], dtype=np.float32)
        vid, _ = tracker.on_entry(track_id=1, embedding=emb, frame_time_s=0.0)
        tracker.on_exit(track_id=1, timestamp_s=60.0)
        tracker.on_entry(track_id=2, embedding=emb, frame_time_s=120.0)
        assert tracker.get_session_seq(vid) == 2

    def test_find_reentry_match_none_embedding(self):
        tracker = ReIDTracker()
        assert tracker._find_reentry_match(None, 0.0) is None

    def test_find_reentry_match_empty_embedding(self):
        tracker = ReIDTracker()
        assert tracker._find_reentry_match(np.array([]), 0.0) is None
