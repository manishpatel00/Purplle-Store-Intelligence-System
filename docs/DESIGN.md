# DESIGN.md — System Architecture

## Overview

The Purplle Store Intelligence System transforms raw CCTV footage into real-time, actionable retail analytics. It is designed as a modular, containerised pipeline that runs entirely via `docker compose up` with zero manual steps.

```
📹 Raw CCTV    →   🔍 Detection Layer   →   ⚡ Event Stream   →   🧠 Intelligence API   →   📊 Live Dashboard
   (clips)          (YOLOv8s + ByteTrack)    (JSONL events)       (FastAPI + PostgreSQL)      (React + WebSocket)
```

The system serves a single **North Star Metric**: **Offline Store Conversion Rate** — the ratio of visitors who completed a purchase to total unique visitors in a session window.

---

## 1. Detection Layer (Pipeline)

The pipeline processes 20-minute CCTV clips from 3 camera angles per store and emits structured behavioural events.

### Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Object Detection | YOLOv8s (22MB, ~3ms/frame) | Detect people (class 0) at 5fps stride |
| Tracking | ByteTrack (IoU-based) | Link detections across frames; assign `track_id` |
| Re-ID | Cosine similarity embeddings | Cross-camera visitor identity; prevent double-counting |
| Staff Classification | HSV colour matching (purple uniform) | Flag `is_staff=true` to exclude from business metrics |
| Spatial Mapping | supervision LineZone + PolygonZone | Entry/exit line crossing; zone dwell detection |
| Session Management | In-memory session store | Track visitor journeys; emit ENTRY/EXIT/ZONE events |

### Edge Case Handling

- **Group Entry**: ByteTrack assigns separate `track_id` per person before line crossing. We emit N individual ENTRY events for N people — never merge.
- **Re-entry**: Cosine similarity check against recent exits within a 900s window. Matches produce `REENTRY` instead of duplicate `ENTRY`.
- **Cross-Camera Dedup**: A per-store `CrossCameraDeduplicator` locks visitor IDs for a handoff window (20s) when they appear on overlapping cameras.
- **Clip-End Flush**: Open sessions without EXIT are auto-closed with `close_reason='clip_end'` to prevent ghost sessions.
- **Partial Occlusion**: Low-confidence detections (< 0.45) are still emitted with `low_confidence_reason` in metadata — never silently dropped.

### Output

An append-only JSONL file per clip, validated against the `BehaviourEvent` Pydantic schema before ingestion.

---

## 2. Event Schema

Every event is a self-contained JSON object with a globally unique `event_id` (UUID v4). Events are linked by `visitor_id` (session key) and ordered by `timestamp` + `session_seq`.

```json
{
  "event_id": "uuid-v4",
  "store_id": "STORE_BLR_002",
  "camera_id": "CAM_ENTRY_01",
  "visitor_id": "VIS_c8a2f1",
  "event_type": "ZONE_DWELL",
  "timestamp": "2026-04-10T14:22:10Z",
  "zone_id": "SKINCARE",
  "dwell_ms": 8400,
  "is_staff": false,
  "confidence": 0.91,
  "metadata": { "queue_depth": null, "sku_zone": "MOISTURISER", "session_seq": 5 }
}
```

8 event types cover the full visitor journey: `ENTRY`, `EXIT`, `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`, `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `REENTRY`.

---

## 3. Intelligence API

### Technology Stack
- **Framework**: FastAPI (async ASGI) with automatic OpenAPI docs at `/docs`
- **Database**: PostgreSQL 15 via asyncpg + SQLModel ORM
- **Cache**: Redis for WebSocket pub/sub and rate limiting
- **Observability**: structlog (JSON), trace IDs via ContextVars, Prometheus metrics

### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/events/ingest` | POST | Batch event ingestion (up to 500 events, idempotent by event_id) |
| `/api/v1/stores/{id}/metrics` | GET | Real-time KPIs: unique visitors, conversion rate, zone dwell, queue depth |
| `/api/v1/stores/{id}/funnel` | GET | 4-stage conversion funnel with drop-off percentages |
| `/api/v1/stores/{id}/anomalies` | GET | Active anomalies with severity levels and suggested actions |
| `/health` | GET | Service health, last event timestamp, stale feed detection |
| `/ws/updates` | WS | Real-time event streaming to dashboard via WebSocket |

### Anomaly Detection Rules
1. **BILLING_QUEUE_SPIKE**: Queue depth ≥ 5 (WARN at 5, CRITICAL at 8)
2. **HIGH_ABANDONMENT**: Billing queue abandonment > 30%
3. **DEAD_ZONE**: No zone visits in 30+ minutes
4. **LOW_FOOTFALL**: Below average hourly visitors
5. **STALE_FEED**: No events received in 10+ minutes

---

## 4. Live Dashboard

React + TypeScript SPA served via Nginx in Docker. Connects to the API via HTTP polling (15s intervals) and WebSocket for live event streaming.

### Pages
1. **Overview**: KPI cards (footfall, conversion, dwell, queue), hourly footfall chart, zone dwell heatmap, live event feed
2. **Conversion Funnel**: Visual funnel showing Entry → Zone Visit → Billing → Purchase with drop-off percentages
3. **Queue Intelligence**: SVG gauge for queue depth, threshold bar, abandonment rate, staff recommendations
4. **Anomaly Center**: Severity-coloured anomaly cards with suggested actions; animated "all clear" state

---

## 5. Containerisation

```yaml
# docker-compose.yml services
postgres  → PostgreSQL 15 (internal network only — not exposed to host)
redis     → Redis Alpine (session cache, WebSocket pub/sub)
api       → FastAPI + Uvicorn (healthcheck: GET /health)
dashboard → Nginx serving React build (port 5173)
```

Network isolation: PostgreSQL and Redis are on an `internal` bridge network. Only the API and dashboard are on the `public` network with host port bindings.

---

## 6. AI-Assisted Decisions

### Decision 1: NMS Threshold Per Camera (AI suggestion: agreed and implemented)

**Situation**: During initial testing, the billing camera undercounted people in the queue. YOLO's default NMS threshold (0.45) was merging bounding boxes of people standing close together.

**AI Suggestion**: Claude recommended lowering the NMS threshold specifically for billing cameras to 0.25, while keeping the default for entry cameras where strict NMS prevents false positives from shadows and reflections.

**Outcome**: I agreed and implemented per-camera detection overrides in the YAML configuration. This improved queue depth accuracy significantly without introducing false positives at the entry line. The insight that NMS should be *contextual* (different cameras have different crowd densities) was valuable and non-obvious.

### Decision 2: Session-First vs Flat Event Schema (AI suggestion: disagreed)

**Situation**: When designing the event schema, I needed to decide between emitting self-contained flat events (one JSON per detection) or session-aggregated events (one JSON per visitor journey).

**AI Suggestion**: Claude recommended session-first, arguing it simplifies funnel computation and prevents orphaned events. GPT-4 suggested flat events but with a `SessionComplete` aggregate event at EXIT time.

**My Decision**: I chose flat events without session aggregates. The live dashboard requires streaming updates — session-first forces waiting until EXIT to emit anything. Flat events stream immediately, and the API reconstructs sessions on-demand via SQL GROUP BY on `visitor_id`. This made the dashboard genuinely real-time rather than batch-delayed. See CHOICES.md for the full analysis.

### Decision 3: Async PostgreSQL vs SQLite (AI suggestion: partially agreed)

**Situation**: Both Claude and GPT-4 initially suggested SQLite for simplicity ("just get it working for a take-home challenge"). I evaluated this against the production-readiness scoring criteria.

**AI Suggestion**: Use SQLite initially, then upgrade to PostgreSQL if needed.

**My Decision**: I went directly to PostgreSQL with asyncpg. The scoring rubric emphasises "production-aware" architecture (20 pts), and SQLite fails three specific criteria: (1) no concurrent writes during batch ingest, (2) no partial indexes for `is_staff=FALSE` customer queries, (3) no WebSocket-compatible async driver. The overhead of PostgreSQL is fully mitigated by Docker Compose — `make up` starts everything. I agreed with the AI on one point: SQLModel provides a clean ORM abstraction that made the SQLite→PostgreSQL migration a single connection string change.

---

## 7. Testing Strategy

- **71.76% statement coverage** (exceeds 70% threshold)
- **35 tests** covering: ingestion idempotency, empty store, all-staff clips, funnel deduplication, anomaly detection, schema validation, queue depth tracking
- **Transactional test isolation**: Each test runs inside a rolled-back transaction — no state bleeds between tests
- **Fixture-driven**: 7 JSONL fixture files covering all scoring edge cases (group entry, re-entry, camera overlap, staff movement, queue buildup, empty store, partial occlusion)
