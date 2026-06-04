#!/usr/bin/env bash
# Link Purplle challenge datasets (Store 1/2 clips + POS CSV) into store-intelligence/data/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EAGLEVIEW="$(cd "$ROOT/.." && pwd)"
CLIPS="$ROOT/data/clips"
POS_DST="$ROOT/data/pos_transactions.csv"

mkdir -p "$CLIPS"

link_clips() {
  local src_dir="$1"
  local label="$2"
  if [ ! -d "$src_dir" ]; then
    echo "[skip] $label not found: $src_dir"
    return
  fi
  local count=0
  while IFS= read -r -d '' f; do
    base="$(basename "$f")"
    dest="$CLIPS/${label}_${base}"
    if [ ! -e "$dest" ]; then
      ln -sf "$f" "$dest"
      count=$((count + 1))
    fi
  done < <(find "$src_dir" -maxdepth 1 \( -name '*.mp4' -o -name '*.avi' -o -name '*.mkv' \) -print0)
  echo "[ok] $label: linked $count clip(s) into $CLIPS"
}

link_clips "$EAGLEVIEW/Store 1" "store1"
link_clips "$EAGLEVIEW/Store 2" "store2"

POS_SRC="$EAGLEVIEW/POS - sample transactionsb1e826f.csv"
if [ -f "$POS_SRC" ]; then
  cp "$POS_SRC" "$POS_DST"
  echo "[ok] POS CSV → $POS_DST"
elif [ -f "$ROOT/data/pos_transactions.csv" ]; then
  echo "[ok] POS CSV already at $POS_DST"
else
  echo "[warn] POS file not found at $POS_SRC"
fi

echo ""
echo "Data ready. Run pipeline:"
echo "  cd $ROOT"
echo "  python -m pipeline.detect --clips-dir ./data/clips --store-id STORE_BLR_002 \\"
echo "    --start-time 2026-04-10T10:00:00Z --output ./data/events.jsonl"
echo "  bash pipeline/run.sh ./data/clips STORE_BLR_002 2026-04-10T10:00:00Z"
