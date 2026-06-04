"""
pipeline/emit.py — Event schema + JSONL writer
Purplle Store Intelligence Challenge 2026
"""

import json
import uuid
from datetime import UTC, datetime


def build_event(
    event_type: str,
    store_id: str,
    camera_id: str,
    visitor_id: str,
    timestamp: str,
    zone_id: str | None = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 0.9,
    queue_depth: int | None = None,
    sku_zone: str | None = None,
    session_seq: int = 0,
) -> dict:
    """Returns an event matching the required Purplle schema."""
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": round(float(confidence), 4),
        "metadata": {
            "queue_depth": queue_depth,
            "sku_zone": sku_zone,
            "session_seq": session_seq,
        },
    }


def compute_timestamp(clip_start_iso: str, frame_idx: int, fps: float) -> str:
    """Convert frame index to ISO-8601 UTC timestamp."""
    start = datetime.fromisoformat(clip_start_iso.replace("Z", "+00:00"))
    ts = start.timestamp() + (frame_idx / max(fps, 1.0))
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_events_jsonl(events: list, output_path: str):
    """Write events list to a JSONL file (overwrites)."""
    with open(output_path, "w") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def append_events_jsonl(events: list, output_path: str):
    """Append events to an existing JSONL file."""
    with open(output_path, "a") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")
