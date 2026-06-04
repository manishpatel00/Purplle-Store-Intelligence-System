# Docker verification checklist

Run when Docker Desktop is available:

```bash
docker compose up --build -d
curl http://localhost:8000/health
curl http://localhost:5173/health          # proxied via dashboard nginx
curl http://localhost:5173/api/v1/stores/STORE_BLR_002/metrics
python3 -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 50
```

Expected:

- API healthy on port 8000
- Dashboard on port 5173 loads and shows metrics (same-origin API proxy)
- WebSocket at `ws://localhost:5173/ws/updates` connects when events are ingested

If Docker is unavailable, use `make local-api` + `make demo` (SQLite, no containers).
