# Purplle Store Intelligence — Submission Reference

**HackerEarth:** Purplle Tech Challenge 2026 | Round 2
**Team:** Manish's Team 2
**Store:** Brigade Road, Bangalore (STORE_BLR_002 / ST1008)
**Date:** April 10, 2026

---

## Quick Submission Fill-In

### Title
Purplle Store Intelligence System — AI-Powered CCTV Analytics API

### Description
> End-to-end AI system converting raw CCTV footage into real-time retail KPIs for Purplle's Brigade Road, Bangalore store.

**What it does:**
- 🎥 **Processes 5 CCTV camera feeds** (CAM 1–5) using YOLOv8m + ByteTrack — detecting, tracking, and uniquely identifying every visitor
- 🧠 **Excludes staff automatically** via HSV color matching on Purplle's distinctive purple uniform (H:130–170°)
- 🔄 **Handles re-entry** using cosine-similarity appearance embeddings — same person leaving and returning counts as 1 unique visitor
- 📊 **REST API** (FastAPI + SQLite) with 5 production-ready endpoints
- 🚨 **Live anomaly detection** — queue spikes, high abandonment, dead zones, stale feeds
- 📺 **Rich terminal dashboard** — real-time KPIs, zone dwell heatmap, funnel visualization

**Results from real CCTV footage (April 10, 2026):**
- 150 unique visitors detected
- 16.0% conversion rate (matches POS: 24 orders ÷ 150 visitors)
- Top zones: Swiss Beauty, Good Vibes, Faces Canada
- Peak hours: 15:00 (33 visitors), 16:00 (42 visitors), 19:00 (43 visitors)

**Tech Stack:** Python · YOLOv8m · ByteTrack · supervision · FastAPI · PostgreSQL (asyncpg) · Docker · Rich

### Theme
AI/ML · Retail Analytics · Computer Vision

### Instructions to Run

```
# 1. Clone / unzip source code
cd store-intelligence

# 2. Start everything with Docker (recommended — no manual steps)
docker compose up -d

# 3. Wait ~15 seconds, then verify:
curl http://localhost:8000/health
curl "http://localhost:8000/api/v1/stores/STORE_BLR_002/metrics"

# 4. (Optional) Run pipeline on real CCTV clips:
python -m pipeline.detect \
    --clips-dir ./data/clips \
    --store-id STORE_BLR_002 \
    --start-time 2026-04-10T10:00:00Z \
    --output ./data/events.jsonl

# 5. (Optional) Start live terminal dashboard:
pip install rich httpx
python dashboard/app.py

# 6. Run tests (coverage >70%):
pip install -r requirements.api.txt pytest pytest-asyncio coverage
coverage run -m pytest tests/ -v
coverage report --fail-under=70
```

### Demo Link
http://localhost:8000/docs  (Swagger UI — run locally)

### Key API Endpoints
- GET  /health
- GET  /api/v1/stores/STORE_BLR_002/metrics
- GET  /api/v1/stores/STORE_BLR_002/funnel
- GET  /api/v1/stores/STORE_BLR_002/anomalies
- POST /api/v1/events/ingest
