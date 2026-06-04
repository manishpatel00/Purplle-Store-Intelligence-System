#!/usr/bin/env bash
# Run FastAPI locally with SQLite — no Docker required.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.api.txt

export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./data/store_intelligence.db}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

mkdir -p data
echo "Starting API on http://localhost:8000 (DB: $DATABASE_URL)"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
