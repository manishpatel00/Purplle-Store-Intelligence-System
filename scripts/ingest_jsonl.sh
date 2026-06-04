#!/usr/bin/env bash
# Batch-ingest a JSONL event file into the running API.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

JSONL="${1:-./data/events_cctv_final.jsonl}"
API_URL="${API_URL:-http://localhost:8000}"
BATCH=100

if [ ! -f "$JSONL" ]; then
  echo "ERROR: File not found: $JSONL"
  exit 1
fi

if [ -x .venv/bin/python3 ]; then PY=".venv/bin/python3"; else PY="python3"; fi

echo "▶ Validating schema: $JSONL"
"$PY" -m pipeline.validate_schema "$JSONL"

echo "▶ Ingesting to $API_URL"
API_URL="$API_URL" JSONL="$JSONL" BATCH="$BATCH" "$PY" <<'PYEOF'
import json
import os
import sys
import httpx

path = os.environ["JSONL"]
api = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
batch_size = int(os.environ.get("BATCH", "100"))

events = []
with open(path) as f:
    for line in f:
        line = line.strip()
        if line:
            events.append(json.loads(line))

total = len(events)
accepted = 0
for i in range(0, total, batch_size):
    batch = events[i : i + batch_size]
    r = httpx.post(f"{api}/api/v1/events/ingest", json=batch, timeout=60)
    r.raise_for_status()
    data = r.json()
    accepted += data.get("accepted", 0)

print(f"Ingested {accepted}/{total} events from {path}")
PYEOF

echo "▶ Metrics snapshot"
curl -sf "$API_URL/api/v1/stores/STORE_BLR_002/metrics?target_date=2026-04-10" | "$PY" -m json.tool 2>/dev/null || true
