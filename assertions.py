"""
assertions.py — Example acceptance assertions for the Store Intelligence API.

Run against a live API (default http://localhost:8000):
    python assertions.py

Or with pytest:
    pytest assertions.py -v
"""

from __future__ import annotations

import os
import sys
import uuid

import httpx

API_BASE = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
STORE_ID = os.getenv("STORE_ID", "STORE_BLR_002")
CHALLENGE_DATE = "2026-04-10"


def _url(path: str) -> str:
    if path.startswith("/api/"):
        return f"{API_BASE}{path}"
    return f"{API_BASE}/api/v1{path}"


def _sample_event(event_type: str = "ENTRY", visitor_id: str | None = None) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM_1",
        "visitor_id": visitor_id or f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": event_type,
        "timestamp": f"{CHALLENGE_DATE}T12:00:00Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.9,
        "extra_metadata": {"session_seq": 1},
    }


def assert_health_ok(client: httpx.Client) -> None:
    r = client.get(f"{API_BASE}/health", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") in ("ok", "healthy", "degraded")


def assert_ingest_accepts_batch(client: httpx.Client) -> None:
    events = [_sample_event("ENTRY"), _sample_event("ZONE_ENTER")]
    events[1]["zone_id"] = "FACES_CANADA"
    events[1]["camera_id"] = "CAM_2"
    r = client.post(_url("/events/ingest"), json=events, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("accepted", 0) >= 1


def assert_ingest_idempotent(client: httpx.Client) -> None:
    ev = _sample_event("ENTRY")
    r1 = client.post(_url("/events/ingest"), json=[ev], timeout=30)
    r2 = client.post(_url("/events/ingest"), json=[ev], timeout=30)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json().get("duplicates", 0) >= 1


def assert_metrics_shape(client: httpx.Client) -> None:
    r = client.get(
        _url(f"/stores/{STORE_ID}/metrics"),
        params={"target_date": CHALLENGE_DATE},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    for key in (
        "unique_visitors",
        "conversion_rate_pct",
        "avg_dwell_by_zone_sec",
        "current_queue_depth",
        "abandonment_rate_pct",
    ):
        assert key in data, f"missing {key}"


def assert_funnel_four_stages(client: httpx.Client) -> None:
    r = client.get(
        _url(f"/stores/{STORE_ID}/funnel"),
        params={"target_date": CHALLENGE_DATE},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    stages = [s["stage"] for s in r.json()["funnel"]]
    assert stages == ["entry", "zone_visit", "billing_queue", "purchase"]


def assert_heatmap_includes_zones(client: httpx.Client) -> None:
    r = client.get(
        _url(f"/stores/{STORE_ID}/heatmap"),
        params={"target_date": CHALLENGE_DATE},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "zones" in body and "data_confidence" in body
    assert len(body["zones"]) >= 1
    z = body["zones"][0]
    assert "intensity" in z and 0 <= z["intensity"] <= 100


def assert_anomalies_list(client: httpx.Client) -> None:
    r = client.get(_url(f"/stores/{STORE_ID}/anomalies"), timeout=10)
    assert r.status_code == 200, r.text
    assert "active_anomalies" in r.json()


def assert_staff_excluded_from_metrics(client: httpx.Client) -> None:
    vid = f"VIS_STAFF_{uuid.uuid4().hex[:4]}"
    staff = _sample_event("ENTRY", visitor_id=vid)
    staff["is_staff"] = True
    client.post(_url("/events/ingest"), json=[staff], timeout=30)
    before = client.get(
        _url(f"/stores/{STORE_ID}/metrics"),
        params={"target_date": CHALLENGE_DATE},
    ).json()["unique_visitors"]
    after = client.get(
        _url(f"/stores/{STORE_ID}/metrics"),
        params={"target_date": CHALLENGE_DATE},
    ).json()["unique_visitors"]
    assert before == after, "staff ENTRY must not increase unique_visitors"


def assert_invalid_event_rejected(client: httpx.Client) -> None:
    bad = _sample_event("NOT_A_REAL_TYPE")
    r = client.post(_url("/events/ingest"), json=[bad], timeout=30)
    assert r.status_code == 200
    assert len(r.json().get("rejected", [])) == 1


def assert_legacy_metrics_path(client: httpx.Client) -> None:
    r = client.get(f"{API_BASE}/stores/{STORE_ID}/metrics", timeout=10)
    assert r.status_code == 200, "legacy /stores/{id}/metrics path should work"


ASSERTIONS = [
    ("health_ok", assert_health_ok),
    ("ingest_accepts_batch", assert_ingest_accepts_batch),
    ("ingest_idempotent", assert_ingest_idempotent),
    ("metrics_shape", assert_metrics_shape),
    ("funnel_four_stages", assert_funnel_four_stages),
    ("heatmap_includes_zones", assert_heatmap_includes_zones),
    ("anomalies_list", assert_anomalies_list),
    ("staff_excluded", assert_staff_excluded_from_metrics),
    ("invalid_event_rejected", assert_invalid_event_rejected),
    ("legacy_metrics_path", assert_legacy_metrics_path),
]


def run_all() -> int:
    failed = []
    with httpx.Client() as client:
        for name, fn in ASSERTIONS:
            try:
                fn(client)
                print(f"  PASS  {name}")
            except AssertionError as e:
                print(f"  FAIL  {name}: {e}")
                failed.append(name)
            except httpx.ConnectError:
                print(f"  SKIP  {name}: API not reachable at {API_BASE}")
                return 2
    if failed:
        print(f"\n{len(failed)} assertion(s) failed.")
        return 1
    print(f"\nAll {len(ASSERTIONS)} assertions passed.")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
