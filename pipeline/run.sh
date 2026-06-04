#!/bin/bash
# pipeline/run.sh — One-command pipeline: process CCTV clips → emit events → ingest to API
# Purplle Store Intelligence System
#
# Usage:
#   ./pipeline/run.sh [clips_dir] [store_id] [start_time]
#
# Examples:
#   ./pipeline/run.sh "./data/clips" STORE_BLR_002 2026-04-10T10:00:00Z
#   ./pipeline/run.sh  (uses defaults)

set -euo pipefail

# ---- Config ----
CLIPS_DIR="${1:-./data/clips}"
STORE_ID="${2:-STORE_BLR_002}"
START_TIME="${3:-2026-04-10T10:00:00Z}"
OUTPUT="./data/events.jsonl"
API_URL="${API_URL:-http://localhost:8000}"
POS_CSV="${4:-./data/pos_transactions.csv}"
LAYOUT="${5:-./store_layout.json}"

echo "=============================================="
echo "  Purplle Store Intelligence Pipeline"
echo "  Store: $STORE_ID"
echo "  Clips: $CLIPS_DIR"
echo "  Start: $START_TIME"
echo "=============================================="

# ---- Create output dirs ----
mkdir -p "$(dirname "$OUTPUT")"
mkdir -p "$CLIPS_DIR"

# ---- Run detection + event generation ----
echo ""
echo "▶ Running detection pipeline..."
python3 -m pipeline.detect \
    --clips-dir "$CLIPS_DIR" \
    --store-id "$STORE_ID" \
    --start-time "$START_TIME" \
    --output "$OUTPUT" \
    --layout "$LAYOUT" \
    --pos-csv "$POS_CSV"

if [ ! -f "$OUTPUT" ]; then
    echo "[ERROR] No events file generated at $OUTPUT"
    exit 1
fi

EVENT_COUNT=$(wc -l < "$OUTPUT")
echo ""
echo "✓ Generated $EVENT_COUNT events → $OUTPUT"

# ---- Wait for API to be ready ----
echo ""
echo "▶ Checking API health..."
MAX_WAIT=30
WAIT=0
until curl -sf "$API_URL/health" > /dev/null 2>&1; do
    if [ $WAIT -ge $MAX_WAIT ]; then
        echo "[WARN] API not reachable at $API_URL — skipping ingest"
        echo "   Start API with: docker compose up  OR  uvicorn app.main:app"
        exit 0
    fi
    sleep 2
    WAIT=$((WAIT + 2))
    echo "  Waiting for API... ($WAIT/${MAX_WAIT}s)"
done
echo "✓ API is ready at $API_URL"

# ---- Batch ingest events in chunks of 100 ----
echo ""
echo "▶ Ingesting events to API..."

BATCH_SIZE=100
TOTAL=0
ACCEPTED=0
FAILED=0

# Split JSONL into batches and POST
python3 - <<'PYEOF'
import json
import sys
import httpx

OUTPUT = "./data/events.jsonl"
API_URL = __import__("os").getenv("API_URL", "http://localhost:8000")
BATCH_SIZE = 100

events = []
with open(OUTPUT) as f:
    for line in f:
        line = line.strip()
        if line:
            events.append(json.loads(line))

total = len(events)
accepted = 0
rejected = 0
duplicates = 0

for i in range(0, total, BATCH_SIZE):
    batch = events[i:i+BATCH_SIZE]
    try:
        r = httpx.post(f"{API_URL}/api/v1/events/ingest", json=batch, timeout=30)
        if r.status_code == 200:
            data = r.json()
            accepted += data.get("accepted", 0)
            rejected += len(data.get("rejected", []))
            duplicates += data.get("duplicates", 0)
        else:
            print(f"[ERROR] Batch {i//BATCH_SIZE + 1} failed: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"[ERROR] Batch {i//BATCH_SIZE + 1} exception: {e}")

print(f"\n✓ Ingest complete:")
print(f"  Total events: {total}")
print(f"  Accepted:     {accepted}")
print(f"  Rejected:     {rejected}")
print(f"  Duplicates:   {duplicates}")
PYEOF

# ---- Verify metrics endpoint ----
echo ""
echo "▶ Verifying metrics endpoint..."
METRICS=$(curl -sf "$API_URL/api/v1/stores/$STORE_ID/metrics" 2>/dev/null || curl -sf "$API_URL/stores/$STORE_ID/metrics" 2>/dev/null || echo '{"error":"unreachable"}')
echo "GET /api/v1/stores/$STORE_ID/metrics:"
echo "$METRICS" | python3 -m json.tool 2>/dev/null || echo "$METRICS"

echo ""
echo "=============================================="
echo "  Pipeline complete!"
echo "  Dashboard: python dashboard/app.py"
echo "  API Docs:  $API_URL/docs"
echo "=============================================="
