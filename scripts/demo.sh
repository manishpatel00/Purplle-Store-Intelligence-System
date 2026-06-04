#!/usr/bin/env bash
# Smoke demo: health check → replay fixtures → metrics → assertions
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
API_URL="${API_URL:-http://localhost:8000}"

if [ -x .venv/bin/python3 ]; then
  PY=".venv/bin/python3"
elif [ -x venv/bin/python3 ]; then
  PY="venv/bin/python3"
else
  PY="python3"
fi

echo "=== Store Intelligence Demo ==="
echo "API: $API_URL"
echo ""

echo "▶ Health check"
curl -sf "$API_URL/health" | "$PY" -m json.tool || {
  echo "ERROR: API not reachable. Start it with: make local-api"
  exit 1
}
echo ""

echo "▶ Replay edge-case fixtures"
"$PY" -m pipeline.replay --jsonl tests/fixtures/group_entry.jsonl --speed 50 --api-url "$API_URL"
"$PY" -m pipeline.replay --jsonl tests/fixtures/queue_buildup.jsonl --speed 50 --api-url "$API_URL"
"$PY" -m pipeline.replay --jsonl tests/fixtures/reentry.jsonl --speed 50 --api-url "$API_URL"
echo ""

echo "▶ Metrics"
curl -sf "$API_URL/api/v1/stores/STORE_BLR_002/metrics?target_date=2026-04-10" | "$PY" -m json.tool
echo ""

echo "▶ Assertions"
API_URL="$API_URL" "$PY" assertions.py
echo ""
echo "Demo complete. Dashboard: cd frontend && npm run dev → http://localhost:5173"
