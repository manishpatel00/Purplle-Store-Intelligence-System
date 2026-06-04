"""
pipeline/sessions.py — Session flushing, staleness garbage collection, and queue/deduplication tracking
Purplle Store Intelligence Challenge 2026
"""

from datetime import datetime, timedelta

from pipeline.emit import build_event


def parse_ts(ts) -> datetime:
    """Safely parse string timestamp to datetime object."""
    if isinstance(ts, str):
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ts


class CrossCameraDeduplicator:
    """
    Locks visitor_ids across overlapping cameras.
    Prevents double-counting a visitor entering overlapping zones in Store 2.
    """

    def __init__(self, handoff_window_seconds: int):
        self._locked: dict[str, datetime] = {}  # visitor_id -> lock_expires
        self._window = timedelta(seconds=handoff_window_seconds)

    def is_duplicate(self, visitor_id: str, ts_str: str) -> bool:
        ts = parse_ts(ts_str)
        expiry = self._locked.get(visitor_id)
        return expiry is not None and ts < expiry

    def lock(self, visitor_id: str, ts_str: str) -> None:
        ts = parse_ts(ts_str)
        self._locked[visitor_id] = ts + self._window

    def gc(self, now_str: str) -> None:
        """Remove expired locks to prevent unbounded memory growth."""
        now = parse_ts(now_str)
        expired = [k for k, exp in self._locked.items() if exp < now]
        for k in expired:
            del self._locked[k]


class QueueDepthTracker:
    """
    Maintains current queue depth as a running integer per billing zone.
    API queries retrieve the most recent BILLING_QUEUE_JOIN event's queue_depth value.
    """

    def __init__(self):
        self._depth: dict[tuple[str, str], int] = {}  # (store_id, zone_id) -> depth

    def join(self, store_id: str, zone_id: str) -> int:
        key = (store_id, zone_id)
        self._depth[key] = self._depth.get(key, 0) + 1
        return self._depth[key]

    def leave(self, store_id: str, zone_id: str) -> int:
        key = (store_id, zone_id)
        self._depth[key] = max(0, self._depth.get(key, 0) - 1)
        return self._depth[key]

    def current(self, store_id: str, zone_id: str) -> int:
        return self._depth.get((store_id, zone_id), 0)


async def flush_all_open_sessions(
    store_id: str, clip_end_ts_str: str, active_sessions: list, reid_tracker
) -> list[dict]:
    """
    Called once when the detection pipeline reaches end-of-clip.
    Closes all sessions that never received an EXIT event.
    Emits a synthetic EXIT with close_reason='clip_end' in metadata.
    """
    events = []
    # Create copy of items to allow deletion during iteration
    for track_id, session in list(reid_tracker.active_sessions.items()):
        event = build_event(
            event_type="EXIT",
            store_id=store_id,
            camera_id=session.last_camera_id,
            visitor_id=session.visitor_id,
            timestamp=clip_end_ts_str,
            confidence=session.last_confidence,
            session_seq=session.session_seq,
        )
        # inject additional metadata for reviewers/auditors
        if "metadata" not in event:
            event["metadata"] = {}
        event["metadata"].update(
            {
                "source_adapter": "clip_end_flush",
                "low_confidence_reason": "clip_end_no_exit",
            }
        )
        events.append(event)

        # Clean up tracker states
        reid_tracker.active_sessions.pop(track_id, None)
        reid_tracker.track_to_visitor.pop(track_id, None)

    return events


async def gc_stale_sessions(
    store_id: str,
    current_time_s: float,
    current_ts_str: str,
    reid_tracker,
    max_duration_seconds: int,
) -> list[dict]:
    """
    Auto-closes sessions older than max_session_duration_seconds.
    Emits a synthetic EXIT event to flush.
    """
    events = []
    cutoff_time_s = current_time_s - max_duration_seconds

    for track_id, session in list(reid_tracker.active_sessions.items()):
        if session.started_at < cutoff_time_s:
            event = build_event(
                event_type="EXIT",
                store_id=store_id,
                camera_id=session.last_camera_id,
                visitor_id=session.visitor_id,
                timestamp=current_ts_str,
                confidence=session.last_confidence,
                session_seq=session.session_seq,
            )
            if "metadata" not in event:
                event["metadata"] = {}
            event["metadata"].update(
                {
                    "source_adapter": "max_session_duration_guard",
                    "low_confidence_reason": "max_session_duration_exceeded",
                }
            )
            events.append(event)

            # Clean up tracker states
            reid_tracker.active_sessions.pop(track_id, None)
            reid_tracker.track_to_visitor.pop(track_id, None)

    return events
