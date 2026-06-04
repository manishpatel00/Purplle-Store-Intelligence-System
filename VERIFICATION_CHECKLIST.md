# Pre-Submission Verification Checklist

Complete this checklist before submitting your work. Each section corresponds to a scoring category.

---

## ✅ Acceptance Gates (Must Pass)

- [ ] **Docker Compose Startup**
  ```bash
  docker compose up --build -d
  sleep 15
  curl http://localhost:8000/health
  # Expected: 200 OK with {"status": "running"}
  ```

- [ ] **API Responds**
  ```bash
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics
  # Expected: 200 OK with JSON (even if zero visitors)
  ```

- [ ] **Documentation Exists**
  ```bash
  ls -la DESIGN.md CHOICES.md README.md
  # All should exist
  ```

---

## Part A: Detection Pipeline (30 pts)

### Entry/Exit Count Accuracy (10 pts)
- [ ] **Group entry test passes**
  ```bash
  pytest tests/test_group_entry_detection.py::test_group_entry_emits_individual_events -v
  # Expected: PASSED (parameterized for group sizes 2,3,4,5)
  ```

- [ ] **ByteTrack produces unique IDs per person**
  - Verified in test: each person gets distinct visitor_id
  - Not merged into "group_entry" pseudo-ID

### Staff Exclusion & Re-entry (10 pts)
- [ ] **Staff marked with is_staff=true**
  ```bash
  pytest tests/test_group_entry_detection.py::test_group_entry_with_staff -v
  # Expected: PASSED
  ```

- [ ] **Re-entry detection test passes**
  ```bash
  pytest tests/test_group_entry_detection.py::test_group_entry_reentry_after_delay -v
  # Expected: PASSED (visitor re-enters after 15 min → REENTRY event)
  ```

- [ ] **Metrics exclude staff from customer count**
  ```bash
  python -m pipeline.replay --jsonl tests/fixtures/staff_movement.jsonl --speed 5
  sleep 5
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics | jq '.unique_visitors'
  # Expected: 0 (all events are is_staff=true)
  ```

### Schema Compliance & Confidence Calibration (10 pts)
- [ ] **All 8 event types accepted**
  ```bash
  pytest tests/test_api_schema_validation.py::TestSchemaCompliance::test_valid_event_schema_all_types -v
  # Expected: 8 PASSED (ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, ZONE_DWELL, BILLING_QUEUE_JOIN, BILLING_QUEUE_ABANDON, REENTRY)
  ```

- [ ] **Low confidence events NOT dropped**
  ```bash
  pytest tests/test_group_entry_detection.py::test_group_entry_low_confidence_handling -v
  # Expected: PASSED (events with 0.42 confidence still emitted)
  ```

- [ ] **Event schema validation**
  ```bash
  pytest tests/test_api_schema_validation.py -v
  # Expected: All TestSchemaCompliance tests PASSED
  ```

---

## Part B: Intelligence API (35 pts)

### API Endpoint Correctness (20 pts)

#### POST /events/ingest
- [ ] Accepts valid events
  ```bash
  pytest tests/test_api_schema_validation.py::test_event_id_uniqueness_enforced -v
  # Expected: PASSED (idempotent by event_id)
  ```

#### GET /metrics
- [ ] Returns all required fields
  ```bash
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics | jq 'keys'
  # Expected: ["store_id", "unique_visitors", "conversion_rate_pct", "avg_dwell_by_zone_sec", "current_queue_depth", "last_updated", "anomalies"]
  ```

#### GET /funnel
- [ ] 4-stage funnel structure
  ```bash
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel | jq '.funnel | length'
  # Expected: 4 (Entry → Zone → Billing → Purchase)
  ```

#### GET /anomalies
- [ ] Returns anomalies array
  ```bash
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/anomalies | jq '.active_anomalies'
  # Expected: [] or list of anomaly objects
  ```

#### GET /heatmap
- [ ] Zone visit frequencies
  ```bash
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/heatmap | jq '.zones'
  # Expected: {"ZONE_A": 45, "ZONE_B": 32, ...}
  ```

#### GET /health
- [ ] Service status
  ```bash
  curl http://localhost:8000/health | jq '.status'
  # Expected: "running"
  ```

### Funnel Accuracy & Session Deduplication (10 pts)
- [ ] Re-entry NOT double-counted
  ```bash
  pytest tests/test_funnel.py::test_funnel_reentry_not_double_counted -v
  # Expected: PASSED
  ```

- [ ] Conversion rate correct
  ```bash
  pytest tests/test_metrics.py -v -k conversion
  # Expected: All conversion tests PASSED
  ```

### Anomaly Detection (5 pts)
- [ ] Queue spike detected
  ```bash
  python -m pipeline.replay --jsonl tests/fixtures/queue_buildup.jsonl --speed 5 &
  sleep 8
  curl http://localhost:8000/api/v1/stores/STORE_BLR_002/anomalies | jq '.active_anomalies[]'
  # Expected: BILLING_QUEUE_SPIKE in results
  ```

- [ ] Anomaly tests pass
  ```bash
  pytest tests/test_anomalies.py -v
  # Expected: All anomaly detection tests PASSED
  ```

---

## Part C: Production Readiness (20 pts)

### Containerization & README (5 pts)
- [ ] Docker Compose works
  ```bash
  docker compose down -v
  docker compose up --build -d
  sleep 15
  docker compose ps
  # Expected: All services "running"
  ```

- [ ] README exists and is complete
  ```bash
  wc -l README.md
  # Expected: >200 lines
  grep -i "quick start" README.md
  # Expected: Found (Quick Start section exists)
  ```

- [ ] Setup in ≤5 commands documented
  ```bash
  head -50 README.md | grep -A 10 "Quick Start"
  # Expected: Clear 5-command setup
  ```

### Structured Logging & Health (5 pts)
- [ ] Health endpoint works
  ```bash
  curl http://localhost:8000/health | jq '.'
  # Expected: {"status": "running", "database": "connected", "redis": "connected", ...}
  ```

- [ ] Logging includes trace_id and store_id
  ```bash
  docker logs store-intelligence-api-1 2>&1 | head -20 | grep -E "trace_id|store_id"
  # Expected: JSON logs with context fields
  ```

- [ ] STALE_FEED warning works
  ```bash
  curl http://localhost:8000/health | jq '.warnings'
  # If no events in 10+ min: should include "STALE_FEED"
  ```

### Test Coverage & Edge Cases (10 pts)
- [ ] Coverage >70%
  ```bash
  pytest tests/ --cov=app,pipeline --cov-report=term-missing | grep TOTAL
  # Expected: TOTAL line shows ≥70%
  ```

- [ ] Edge cases tested
  ```bash
  # Empty store
  pytest tests/test_fixtures_validation.py::TestScenarioEmptyStore -v
  # Expected: PASSED
  
  # All staff
  pytest tests/test_fixtures_validation.py::TestScenarioAllStaff -v
  # Expected: PASSED
  
  # Zero purchases
  pytest tests/test_api_schema_validation.py::test_metrics_zero_purchase_history_valid_response -v
  # Expected: PASSED
  ```

- [ ] Full test suite passes
  ```bash
  pytest tests/ -v
  # Expected: All tests PASSED (81 tests)
  ```

---

## Part D: AI Engineering (15 pts)

### Prompt Blocks in Test Files (5 pts)
- [ ] All test files have PROMPT and CHANGES MADE blocks
  ```bash
  grep -l "# PROMPT:" tests/test_*.py
  # Expected: At least 3 files
  grep -l "# CHANGES MADE:" tests/test_*.py
  # Expected: At least 3 files
  ```

- [ ] Blocks are descriptive
  ```bash
  grep -A 3 "# PROMPT:" tests/test_group_entry_detection.py
  # Expected: Multi-line description of AI prompt
  ```

### DESIGN.md AI-Assisted Decisions (5 pts)
- [ ] Section exists
  ```bash
  grep -i "AI-Assisted Decisions" DESIGN.md
  # Expected: Found
  ```

- [ ] 3+ decisions documented
  ```bash
  grep -c "^## Decision" DESIGN.md
  # Expected: ≥3
  ```

- [ ] >250 words total
  ```bash
  wc -w DESIGN.md
  # Expected: >250
  ```

### CHOICES.md Technical Trade-offs (5 pts)
- [ ] 5+ decisions documented
  ```bash
  grep -c "^## " CHOICES.md
  # Expected: ≥5
  ```

- [ ] Each has: options, AI suggestion, your reasoning
  ```bash
  grep -A 5 "^## " CHOICES.md | head -20
  # Expected: Structure with decision rationale
  ```

- [ ] >250 words total
  ```bash
  wc -w CHOICES.md
  # Expected: >250
  ```

---

## Part E: Live Dashboard Bonus (+10 pts)

### Video Recording Component
- [ ] VideoRecorder.tsx exists
  ```bash
  ls -la frontend/src/components/dashboard/VideoRecorder.tsx
  # Expected: File exists
  ```

- [ ] Can start/stop recording
  ```bash
  cd frontend && npm run dev &
  open http://localhost:5173/live
  # Click "Video Recording" tab
  # Click "Start Camera" button
  # Expected: Camera preview appears
  ```

### Detection Visualization
- [ ] DetectionVisualizer.tsx exists
  ```bash
  ls -la frontend/src/components/dashboard/DetectionVisualizer.tsx
  # Expected: File exists
  ```

- [ ] Canvas renders detections
  ```bash
  # Terminal 1: API
  docker compose up --build -d
  sleep 15
  
  # Terminal 2: Dashboard
  cd frontend && npm run dev
  
  # Terminal 3: Pipeline
  python -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 5
  
  # Terminal 4: Browser
  open http://localhost:5173/live
  # Click "Detection Visualization" tab
  # Expected: Bounding boxes appear on canvas with labels and confidence
  ```

### Live Dashboard Integration
- [ ] Three tabs working
  ```bash
  # Visit http://localhost:5173/live
  # Expected: Three tabs visible:
  #   - Event Stream
  #   - Detection Visualization
  #   - Video Recording
  ```

- [ ] Real-time updates
  ```bash
  # While pipeline replay running:
  # Expected: Metrics update every 1-2 seconds
  #           Bounding boxes appear on canvas
  #           Event table shows new events
  ```

- [ ] WebSocket connection active
  ```bash
  open http://localhost:5173
  # DevTools → Network → WS
  # Expected: ws://localhost:5173/ws/updates connection shows "101 Switching Protocols"
  ```

---

## File Checklist

### Core Files
- [ ] DESIGN.md (>250 words, AI decisions)
- [ ] CHOICES.md (>250 words, 5+ trade-offs)
- [ ] README.md (setup in 5 commands)
- [ ] SUBMISSION_IMPROVEMENTS.md (40+ page detailed guide)
- [ ] TESTING_GUIDE.md (comprehensive test documentation)

### Code Files
- [ ] `tests/test_group_entry_detection.py` (8 test methods)
- [ ] `tests/test_api_schema_validation.py` (30+ tests)
- [ ] `tests/test_fixtures_validation.py` (10+ tests per fixture)
- [ ] `frontend/src/components/dashboard/VideoRecorder.tsx`
- [ ] `frontend/src/components/dashboard/DetectionVisualizer.tsx`
- [ ] `frontend/src/pages/LivePage.tsx` (updated with tabs)

### Test Fixtures
- [ ] `tests/fixtures/group_entry.jsonl`
- [ ] `tests/fixtures/reentry.jsonl`
- [ ] `tests/fixtures/queue_buildup.jsonl`
- [ ] `tests/fixtures/staff_movement.jsonl`
- [ ] `tests/fixtures/all_staff.jsonl`
- [ ] `tests/fixtures/camera_overlap.jsonl`
- [ ] `tests/fixtures/empty_store.jsonl`
- [ ] `tests/fixtures/partial_occlusion.jsonl`
- [ ] `tests/fixtures/pos_sample.csv`
- [ ] `tests/fixtures/pos_correlation.csv`

### Configuration Files
- [ ] `docker-compose.yml` (services defined)
- [ ] `Makefile` (targets for test, coverage, validate, replay)
- [ ] `.env.example` (env vars documented)
- [ ] `pyproject.toml` (linter + typecheck config)

---

## Scoring Summary

| Category | Points | Status | Notes |
|----------|--------|--------|-------|
| Part A: Detection | 30 | ✅ | Group entry, staff, re-entry, schema |
| Part B: API | 35 | ✅ | 6 endpoints, funnel, anomalies |
| Part C: Production | 20 | ✅ | Docker, logging, >70% coverage |
| Part D: AI Engineering | 15 | ✅ | Prompt blocks, DESIGN.md, CHOICES.md |
| **Part E: Bonus** | **+10** | ✅ | Video recording, detection viz, live dashboard |
| **TOTAL** | **110** | ✅ | 100 pts + 10 bonus |

---

## Final Checks (Run Before Submitting)

```bash
# 1. Format & lint
make lint

# 2. Type check
make typecheck

# 3. Run full test suite
pytest tests/ -v --cov=app,pipeline --cov-report=term-missing

# 4. Docker build & start
docker compose down -v
docker compose up --build -d
sleep 15

# 5. Verify all endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/funnel
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/anomalies
curl http://localhost:8000/api/v1/stores/STORE_BLR_002/heatmap

# 6. Check documentation
wc -w DESIGN.md CHOICES.md README.md
grep -c "# PROMPT:" tests/test_*.py

# 7. Run quick-start demo
make quick-start
```

Expected result: All checks pass ✅

---

Good luck! 🚀
