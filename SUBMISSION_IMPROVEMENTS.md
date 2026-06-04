# Purplle Store Intelligence — Submission Improvements & Scoring Guide

## Part A: Detection Pipeline (30 points)

### Entry/Exit Count Accuracy (10 pts)
- ✅ **Implemented**: YOLOv8s + ByteTrack with per-camera NMS tuning
- ✅ **Group handling**: ByteTrack assigns unique track_id per person
- ✅ **Cross-camera dedup**: CrossCameraDeduplicator locks visitors for 20s handoff window
- ✅ **Test fixture**: `tests/fixtures/group_entry.jsonl` — 3 people entering at t=10s, t=10s, t=11s
- 🎯 **Verification**: `python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5`

### Staff Exclusion & Re-entry (10 pts)
- ✅ **Staff detection**: HSV color matching on Purplle purple uniform (H:130-170)
- ✅ **Re-entry detection**: Cosine similarity embeddings within 900s window
- ✅ **Test fixtures**:
  - `staff_movement.jsonl` — staff crosses all zones, `is_staff=true` throughout
  - `reentry.jsonl` — visitor exits at t=100s, re-enters at t=950s
- 🎯 **Verification**:
  ```bash
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel | jq '.funnel'
  # Should show: billing_queue_converters excludes staff
  ```

### Schema Compliance & Confidence Calibration (10 pts)
- ✅ **Event schema**: 8 types (ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, BILLING_QUEUE_JOIN, BILLING_QUEUE_ABANDON, REENTRY)
- ✅ **Unique event_id**: UUID v4, globally unique, no duplicates
- ✅ **Timestamps**: ISO-8601 UTC with Z suffix
- ✅ **Low-confidence handling**: Not silently dropped, flagged with `low_confidence_reason` metadata
- ✅ **CLI validation**: `python -m pipeline.validate_schema output/store_001.jsonl`
- 🎯 **Test**: `pytest tests/test_api_schema_validation.py::TestSchemaCompliance -v`

---

## Part B: Intelligence API (35 points)

### API Endpoint Correctness (20 pts)
- ✅ **POST /api/v1/events/ingest**: Idempotent by event_id, partial success support (207 Multi-Status)
- ✅ **GET /api/v1/stores/{id}/metrics**: Real-time KPIs (unique_visitors, conversion_rate, avg_dwell, queue_depth)
- ✅ **GET /api/v1/stores/{id}/funnel**: 4-stage funnel with drop-off %
- ✅ **GET /api/v1/stores/{id}/heatmap**: Zone visit frequency (0-100 normalized)
- ✅ **GET /api/v1/stores/{id}/anomalies**: Active anomalies with severity + suggested_action
- ✅ **GET /health**: Service status, last event timestamp, STALE_FEED warning if >10 min lag
- 🎯 **Test**:
  ```bash
  cd frontend && npm run dev &  # Terminal 1
  python -m pipeline.replay --jsonl tests/fixtures/queue_buildup.jsonl --speed 5 &  # Terminal 2
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics | jq '.'
  open http://localhost:5173  # Watch real-time updates
  ```

### Funnel Accuracy & Session Deduplication (10 pts)
- ✅ **Session unit**: Visitors (not raw events) — grouped by visitor_id + EXIT
- ✅ **Re-entry dedup**: REENTRY events don't create new funnel entry
- ✅ **Funnel stages**: Entry → Zone Visit → Billing Queue → Purchase
- ✅ **Drop-off calc**: (stage_count / entry_count) * 100
- 🎯 **Test**:
  ```bash
  pytest tests/test_funnel.py::test_funnel_reentry_not_double_counted -v
  python -m pipeline.replay --jsonl tests/fixtures/reentry.jsonl --speed 5
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel | jq '.funnel'
  ```

### Anomaly Detection (5 pts)
- ✅ **BILLING_QUEUE_SPIKE**: Depth ≥ 5 for 3+ consecutive minutes
- ✅ **HIGH_ABANDONMENT**: Billing queue abandonment > 30%
- ✅ **DEAD_ZONE**: No visits to any zone in 30+ minutes
- ✅ **Test fixture**: `queue_buildup.jsonl` triggers BILLING_QUEUE_SPIKE
- 🎯 **Test**:
  ```bash
  python -m pipeline.replay --jsonl tests/fixtures/queue_buildup.jsonl --speed 5
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/anomalies | jq '.active_anomalies'
  ```

---

## Part C: Production Readiness (20 points)

### Containerisation & README (5 pts)
- ✅ **Docker Compose**: `docker compose up --build -d` starts everything
- ✅ **No manual steps**: Single command after git clone
- ✅ **README setup**: Explains how to run detection pipeline, where output goes
- 🎯 **Verification**:
  ```bash
  cd /path/to/store-intelligence
  docker compose up --build -d
  sleep 15
  curl http://localhost:8000/health
  # Should return 200 OK
  ```

### Structured Logging & Health (5 pts)
- ✅ **Logging**: JSON format via structlog, includes trace_id, store_id, endpoint, latency_ms, status_code
- ✅ **Health endpoint**: Returns uptime, database status, Redis status, stores list with last_event_at
- ✅ **STALE_FEED warning**: If no events received in 10+ minutes
- 🎯 **Verification**:
  ```bash
  curl http://localhost:8000/health | jq '.'
  # Check logs: docker logs store-intelligence-api-1 | grep "http.request"
  ```

### Test Coverage & Edge Cases (10 pts)
- ✅ **Coverage**: >70% statement coverage (pytest --cov)
- ✅ **Edge cases tested**:
  - Empty store (zero events) → returns 200 OK, metrics show 0 visitors
  - All-staff clip → metrics show 0 customers
  - Zero purchases → conversion_rate = 0.0
  - Re-entry in funnel → not double-counted
  - Low-confidence detections → not silently dropped
- ✅ **Test fixtures**:
  - `all_staff.jsonl` — every event has is_staff=true
  - `empty_store.jsonl` — empty file
  - `partial_occlusion.jsonl` — confidence 0.35-0.55
- 🎯 **Run tests**:
  ```bash
  pytest tests/ -v --cov=app,pipeline --cov-report=html
  open htmlcov/index.html
  ```

---

## Part D: AI Engineering (15 points)

### Prompt Blocks in Test Files
Each test file starts with a comment block showing the AI prompt used and changes made:
- ✅ `tests/test_group_entry_detection.py` — Group entry handling
- ✅ `tests/test_api_schema_validation.py` — Schema compliance
- 🎯 **Example**:
  ```python
  # PROMPT: Create tests for group entry...
  # CHANGES MADE: Split into parameterized fixtures...
  ```

### DESIGN.md: AI-Assisted Decisions Section
- ✅ **Decision 1**: NMS threshold per camera (agreed with AI)
- ✅ **Decision 2**: Session-first vs flat events (disagreed with AI)
- ✅ **Decision 3**: Async PostgreSQL vs SQLite (disagreed with AI)
- 🎯 **Format**: Problem statement, AI suggestion, decision, reasoning (2-3 paragraphs each)

### CHOICES.md: Detailed Reasoning
- ✅ **Decision 1**: YOLOv8s model selection (options considered, trade-offs, why AI's RT-DETR suggestion was overridden)
- ✅ **Decision 2**: Event schema design (flat vs session-first, streaming-first rationale)
- ✅ **Decision 3**: FastAPI + PostgreSQL (async requirements, scoring criteria alignment)
- 🎯 **Format**: Options table, AI suggestion, your choice, 3-4 bullet points of reasoning

---

## Part E: Live Dashboard Bonus (+10 points)

### Video Recording Component
- ✅ **VideoRecorder.tsx**: Captures pipeline output or demo replay
  - Start/Stop camera
  - Record/Stop recording
  - Download WebM file
  - Timer display (HH:MM:SS)
  - Auto-start on LivePage

### Detection Visualization
- ✅ **DetectionVisualizer.tsx**: Renders real-time detections on canvas
  - Bounding boxes per person (color-coded by visitor_id)
  - Confidence labels
  - Staff indicator (dashed box)
  - Event type badges (ENTRY, ZONE_IN, QUEUE, etc.)
  - Zone labels
  - Summary stats (customers, staff, low-conf)

### Live Dashboard Integration
- ✅ **LivePage.tsx**: Three tabs
  - **Event Stream**: WebSocket-fed table of raw events
  - **Detection Viz**: Canvas visualization with stats
  - **Video Recording**: Record pipeline demo
- ✅ **Real-time updates**: WebSocket connection to /ws/updates
- ✅ **Proof**: Run pipeline replay, watch metrics update live

### How to Get Bonus Points
1. Start API and frontend:
   ```bash
   docker compose up --build -d
   cd frontend && npm run dev
   ```

2. Navigate to http://localhost:5173/live

3. Click "Video Recording" tab → Start Camera

4. In another terminal, run pipeline:
   ```bash
   python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5
   ```

5. Watch the canvas show detections, tables update in real-time, video record the session

6. Download the WebM recording

---

## Verification Checklist

### Before Submission
- [ ] `docker compose up --build -d` runs without errors
- [ ] `curl http://localhost:8000/health` returns 200
- [ ] Dashboard at http://localhost:5173 loads
- [ ] All test fixtures replay successfully
- [ ] `pytest tests/ -v` passes with >70% coverage
- [ ] DESIGN.md has "AI-Assisted Decisions" section (>250 words)
- [ ] CHOICES.md has 3 decisions with options, AI suggestion, your reasoning
- [ ] Prompt blocks at top of test files
- [ ] README explains detection pipeline setup in 5 commands or less
- [ ] `.env.example` lists all required env vars

### Scoring Checklist
- **Part A (30 pts)**:
  - [ ] 10 pts: Entry/exit count accuracy (YOLOv8 + ByteTrack)
  - [ ] 10 pts: Staff exclusion + re-entry (tests pass)
  - [ ] 10 pts: Schema compliance + confidence calibration

- **Part B (35 pts)**:
  - [ ] 20 pts: All 6 endpoints working (health, metrics, funnel, heatmap, anomalies, ingest)
  - [ ] 10 pts: Funnel accuracy + re-entry dedup (funnel tests pass)
  - [ ] 5 pts: Anomaly detection (QUEUE_SPIKE, etc.)

- **Part C (20 pts)**:
  - [ ] 5 pts: Docker Compose + README
  - [ ] 5 pts: Structured logging + health
  - [ ] 10 pts: >70% test coverage + edge cases

- **Part D (15 pts)**:
  - [ ] 5 pts: Prompt blocks in test files
  - [ ] 5 pts: DESIGN.md AI decisions
  - [ ] 5 pts: CHOICES.md detailed reasoning

- **Part E (+10 bonus pts)**:
  - [ ] Video recording functional
  - [ ] Detection viz working
  - [ ] Live dashboard shows real-time updates

---

## Quick Start (5 Commands)

```bash
# 1. Clone and enter directory
git clone <repo> && cd store-intelligence

# 2. Set up data (links CCTV clips and POS CSV)
bash scripts/setup_data.sh

# 3. Start Docker containers
docker compose up --build -d

# 4. Wait 15s, verify API health
sleep 15 && curl http://localhost:8000/health

# 5. Run a test fixture and watch metrics update live
python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5 &
open http://localhost:5173  # Dashboard
```

---

## Detailed Running Guide

### Setup

```bash
cd store-intelligence

# Install dependencies (Python API)
pip install -r requirements.api.txt

# Install dependencies (Detection pipeline — optional if not running CV)
# pip install -r requirements.pipeline.txt

# Create .env
cp .env.example .env
```

### Option 1: Docker (Recommended for Submission)

```bash
docker compose up --build -d
sleep 15
curl http://localhost:8000/health
# Dashboard: http://localhost:5173
```

### Option 2: Local (Development)

```bash
# Terminal 1: API
export DATABASE_URL=sqlite+aiosqlite:///./data/store_intelligence.db
uvicorn app.main:app --reload --port 8000

# Terminal 2: Dashboard
cd frontend && npm install && npm run dev
# http://localhost:5173

# Terminal 3: Pipeline (replay test fixture)
python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5
```

### Run All Tests

```bash
pytest tests/ -v --cov=app,pipeline --cov-report=html
open htmlcov/index.html  # See coverage report
```

### Run Specific Test Suites

```bash
# Group entry detection
pytest tests/test_group_entry_detection.py -v

# API schema validation
pytest tests/test_api_schema_validation.py -v

# Full API tests
pytest tests/test_metrics.py tests/test_funnel.py tests/test_heatmap.py -v
```

### Validate Schema Before Ingest

```bash
python -m pipeline.validate_schema data/events_cctv_final.jsonl
```

### Ingest Pre-Generated Events

```bash
# If you have a pre-processed events file
python -c "
import json
from app.models import IngestedEvent
with open('data/events_cctv_final.jsonl') as f:
    for line in f:
        IngestedEvent.parse_raw(line)
print('✅ All events valid')
"
```

---

## Troubleshooting

### `docker compose up` fails
- Ensure Docker Desktop is running
- Check ports 5173, 8000, 5432 are not in use
- Run `docker compose logs` to see errors

### Dashboard shows "API connection failed"
- API container may still be starting
- Wait 15 seconds after `docker compose up`
- Check `docker compose ps` — all should be "running"
- Check CORS: API logs should show "CORS enabled"

### Pipeline replay produces no events
- Ensure test fixtures exist: `ls tests/fixtures/`
- Check file permissions: `file tests/fixtures/group_entry.jsonl`
- Increase speed if running too fast: `--speed 1` for real-time

### Tests fail with "module not found"
- Ensure in correct directory: `cd store-intelligence`
- Install deps: `pip install -r requirements.api.txt pytest-asyncio hypothesis`
- Run from repo root: `pytest tests/`

---

## Expected Output

### Successful Ingest

```bash
$ curl -X POST http://localhost:8000/api/v1/events/ingest \
  -H "Content-Type: application/json" \
  -d '{"events": [{"event_id": "...", "event_type": "ENTRY", ...}]}'

{
  "ingested": 1,
  "deduplicated": 0,
  "errors": [],
  "status": "success"
}
```

### Metrics Response

```bash
$ curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics | jq '.'

{
  "store_id": "STORE_BLR_002",
  "unique_visitors": 24,
  "conversion_rate_pct": 62.5,
  "avg_dwell_by_zone_sec": {
    "SKINCARE": 420,
    "MAKEUP": 380,
    "BILLING": 120
  },
  "current_queue_depth": 3,
  "anomalies": []
}
```

### Funnel Response

```bash
$ curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel | jq '.funnel'

[
  {"stage": "ENTRY", "count": 24, "dropoff_pct": 0},
  {"stage": "ZONE_VISIT", "count": 22, "dropoff_pct": 8.3},
  {"stage": "BILLING_QUEUE", "count": 18, "dropoff_pct": 18.2},
  {"stage": "PURCHASE", "count": 15, "dropoff_pct": 37.5}
]
```

---

Good luck! 🚀
