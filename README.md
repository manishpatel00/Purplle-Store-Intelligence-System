# Store Intelligence API
## Purplle Tech Challenge 2026 — Round 2

AI-powered Store Intelligence System built on CCTV footage from Brigade Road, Bangalore (STORE_BLR_002 / ST1008).

**Stack:** YOLOv8s + ByteTrack · FastAPI · PostgreSQL (async) · React Dashboard · Docker

---

## Quick Start (5 commands)

```bash
git clone <your-repo> store-intelligence
cd store-intelligence
bash scripts/setup_data.sh    # links Store 1/2 CCTV clips + POS CSV from parent folder
docker compose up --build -d    # requires Docker Desktop running
# Wait 15s for API to start, then verify:
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics
```

**Docker not running?** Use the [local path](#local-development-without-docker) below (`make local-api` + `make demo`).

**API:** http://localhost:8000 · **Swagger:** http://localhost:8000/docs · **Dashboard:** http://localhost:5173

### Dashboard (React)

The dashboard polls metrics, funnel, heatmap, and anomalies every 3s and streams ingest events over WebSocket.

```bash
cd frontend && npm install && npm run dev
# With API on :8000 — Vite proxies /api, /health, /ws automatically
```

---

## Quick Demo (watch data flow live)

```bash
make local-api    # terminal 1
make demo         # terminal 2 (or: docker compose up -d && make demo)
```

Docker variant:

```bash
docker compose up --build -d
curl http://localhost:8000/health
# Dashboard at http://localhost:5173 (nginx proxies /api and /ws to backend)
python3 -m pipeline.replay --jsonl tests/fixtures/queue_buildup.jsonl --speed 5
python3 -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5
python3 -m pipeline.replay --jsonl tests/fixtures/reentry.jsonl --speed 5

# 4. Check metrics — should show real visitor counts
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics | python3 -m json.tool

# 5. Check funnel — should show 4-stage conversion funnel
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel | python3 -m json.tool

# 6. Check anomalies — should show queue spike + high abandonment
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/anomalies | python3 -m json.tool

# 7. Open dashboard — watch visitor count, funnel, and queue update live
open http://localhost:5173
```

---


## Local Development (without Docker)

```bash
cd store-intelligence
make setup-data          # symlink Store 1/2 clips + POS CSV
make local-api           # SQLite API on :8000 (new terminal)

# Another terminal:
make demo                # replay fixtures + assertions
# OR ingest pre-generated CCTV events:
make ingest-events       # loads data/events_cctv_final.jsonl

# Dashboard (Vite proxies API — no CORS issues):
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

Manual equivalent:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.api.txt httpx
export DATABASE_URL=sqlite+aiosqlite:///./data/store_intelligence.db
uvicorn app.main:app --reload --port 8000
```

**Pipeline (optional — requires CV libs):**

```bash
pip install -r requirements.pipeline.txt
python -m pipeline.detect --clips-dir ./data/clips --store-id STORE_BLR_002 \
  --start-time 2026-04-10T10:00:00Z --output ./data/events.jsonl
bash pipeline/run.sh ./data/clips STORE_BLR_002 2026-04-10T10:00:00Z
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/events/ingest` | Batch ingest detection events (max 500/request) |
| `GET`  | `/api/v1/stores/{store_id}/metrics` | KPIs: visitors, conversion, dwell, queue depth |
| `GET`  | `/api/v1/stores/{store_id}/funnel` | 4-stage conversion funnel with drop-off rates |
| `GET`  | `/api/v1/stores/{store_id}/anomalies` | Active operational anomalies |
| `GET`  | `/api/v1/stores/{store_id}/heatmap` | Zone dwell heatmap (intensity 0–100) |
| `GET`  | `/health` | API + database + feed freshness (root, not versioned) |
| `GET`  | `/docs` | Swagger UI |

### Example responses

```bash
# Metrics
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics?target_date=2026-04-10
# → {"unique_visitors": 149, "conversion_rate_pct": 16.1, "current_queue_depth": 0, ...}

# Funnel
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel?target_date=2026-04-10
# → {"funnel": [{"stage":"entry","count":149}, ...], "overall_conversion_rate_pct": 16.1}

# Anomalies
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/anomalies
# → {"active_anomalies": [...], "anomaly_count": 0}

# Ingest events
curl -X POST http://localhost:8000/api/v1/events/ingest \
  -H "Content-Type: application/json" \
  -d '[{"event_id":"test-001","store_id":"STORE_BLR_002","camera_id":"CAM_1","visitor_id":"VIS_000001","event_type":"ENTRY","timestamp":"2026-04-10T10:15:00Z","is_staff":false,"confidence":0.94,"metadata":{}}]'
```

---

## Run Tests

```bash
pip install -r requirements.api.txt pytest pytest-asyncio coverage anyio
coverage run -m pytest tests/ -v
coverage report --fail-under=70
```

Expected coverage: **>83%** across all test files (81 tests).

---

## Pipeline: CCTV Processing

Place challenge footage under `../Store 1/` and `../Store 2/` (or run `bash scripts/setup_data.sh` to symlink into `data/clips/`).

```bash
# With real CCTV clips (MP4):
python -m pipeline.detect \
    --clips-dir ./data/clips \
    --store-id STORE_BLR_002 \
    --start-time 2026-04-10T10:00:00Z \
    --output ./data/events.jsonl \
    --model yolov8m.pt

# Then ingest to API:
bash pipeline/run.sh ./data/clips STORE_BLR_002 2026-04-10T10:00:00Z

# Without clips (uses POS-derived synthetic events):
# Drop your POS CSV at ./data/pos_transactions.csv
python -m pipeline.detect --clips-dir ./data/empty_dir --pos-csv ./data/pos_transactions.csv
```

### Camera Mapping

| Camera | File | Type | Zones |
|--------|------|------|-------|
| CAM_1 | CAM 1.mp4 | Entry | ENTRY_EXIT (line crossing) |
| CAM_2 | CAM 2.mp4 | Floor | EB_KOREAN, GOOD_VIBES, DERMDOC, MINIMALIST |
| CAM_3 | CAM 3.mp4 | Floor | MAYBELLINE, FACES_CANADA, NY_BAE, SWISS_BEAUTY |
| CAM_4 | CAM 4.mp4 | Floor | FOH, FRAGRANCE, NAIL_UNIT, MAKEUP_UNIT |
| CAM_5 | CAM 5.mp4 | Billing | CASH_COUNTER, BILLING_QUEUE |

---

## Store: Brigade Road, Bangalore

- **Store ID:** STORE_BLR_002 (legacy: ST1008)
- **Data date:** April 10, 2026
- **POS summary:** 24 orders · 101 items · ₹44,920 GMV
- **Peak hours:** 12:00 and 19:00
- **Top brands:** Faces Canada · Good Vibes · NY Bae · DermDoc

---

## Project Structure

```
store-intelligence/
├── pipeline/
│   ├── detect.py            # Main detection: YOLOv8m + ByteTrack
│   ├── tracker.py           # Re-ID tracker with cosine similarity
│   ├── staff_classifier.py  # HSV uniform detection + embeddings
│   ├── zone_mapper.py       # PolygonZone resolver from layout JSON
│   ├── emit.py              # Event schema + JSONL writer
│   ├── sessions.py          # Session flush, GC, deduplication, queue tracking
│   ├── replay.py            # Event replay with speed multiplier
│   ├── validate_schema.py   # JSONL schema validation CLI
│   ├── synthetic_events.py  # POS-derived synthetic events (fallback)
│   └── run.sh               # One-command: clips → events → ingest
├── app/
│   ├── core/
│   │   ├── settings.py      # Centralized configuration from env vars
│   │   └── tracing.py       # ContextVar-based trace ID propagation
│   ├── main.py              # FastAPI entrypoint + middleware + CORS
│   ├── database.py          # Async PostgreSQL/SQLite engine
│   ├── models.py            # EventDB + VisitorSessionDB + EventCreate schemas
│   ├── ingestion.py         # POST /api/v1/events/ingest
│   ├── metrics.py           # GET /api/v1/stores/{id}/metrics
│   ├── funnel.py            # GET /api/v1/stores/{id}/funnel
│   ├── anomalies.py         # GET /api/v1/stores/{id}/anomalies
│   ├── health.py            # GET /health
│   ├── websocket.py         # WebSocket broadcast manager
│   ├── worker.py            # Redis stream consumer
│   └── metrics_prom.py      # Prometheus /metrics endpoint
├── tests/
│   ├── conftest.py          # Fixtures + in-memory DB + event factory
│   ├── test_pipeline.py     # Ingest endpoint tests
│   ├── test_metrics.py      # Metrics endpoint tests
│   ├── test_funnel.py       # Funnel endpoint tests
│   ├── test_anomalies.py    # Anomaly + health tests
│   └── test_addendum.py     # v3 addendum feature tests
├── docs/
│   ├── DESIGN.md            # System architecture + AI decisions
│   └── CHOICES.md           # 6 technical trade-off documents
├── dashboard/
│   └── app.py               # Rich terminal dashboard
├── store_layout.json        # Brigade Road zone polygons
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.pipeline
├── pyproject.toml           # Linter + typecheck config
├── Makefile                 # make check, make weights, make validate
├── .env.example             # Environment variable template
├── requirements.api.txt
├── requirements.pipeline.txt
└── requirements.txt
```

---

## Key Design Decisions

See [`docs/CHOICES.md`](docs/CHOICES.md) for detailed trade-off reasoning. Summary:

1. **YOLOv8m over RT-DETR** — 2.5x faster for batch processing, ByteTrack handles occlusion
2. **HSV 256-D embeddings over OSNet** — Zero dependency overhead for single-store demo
3. **PostgreSQL with SQLite fallback** — Production-grade with zero-config testing
4. **session_seq as integer** — Pipeline controls ordering, not DB (handles out-of-order ingest)
5. **HSV staff detection over pose** — 40x faster, brand-specific to Purplle uniform color
6. **On-demand anomaly checks** — Simpler REST interface; dashboard polls every 3s

---

## Acceptance Checklist

- [x] `docker compose up` — works when Docker Desktop is running (see [docs/DOCKER_VERIFY.md](docs/DOCKER_VERIFY.md))
- [x] Local fallback — `make local-api` + `make demo` without Docker
- [x] `POST /api/v1/events/ingest` — no 5xx errors
- [x] `GET /api/v1/stores/STORE_BLR_002/metrics` — valid JSON with all fields
- [x] `DESIGN.md` — >250 words, includes AI-Assisted Decisions section
- [x] `CHOICES.md` — >250 words, 6 decisions with personal reasoning
- [x] Every test file has `# PROMPT:` / `# CHANGES MADE:` header block
- [x] Test coverage target >70%
- [x] README setup in ≤5 commands
- [x] Staff excluded from all visitor counts (`is_staff=False` filter)
- [x] Re-entries don't double-count unique visitors
- [x] Live React dashboard at http://localhost:5173 (bonus +10pts)
- [x] Test coverage: 83.77% (81 tests, exceeds 70% gate)
- [x] Bonus: Integrated the beautiful HTML dashboard as a live API client (`dashboard/live_html_dashboard.html`)
