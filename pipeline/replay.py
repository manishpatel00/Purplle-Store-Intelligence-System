"""
pipeline/replay.py — Replay JSONL events into the API at simulated real time
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime

import httpx


def load_jsonl(path: str) -> list:
    """Load and parse JSONL events."""
    events = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("//") and not line.startswith("#"):
                    events.append(json.loads(line))
    except FileNotFoundError:
        print(f"Error: File '{path}' not found.")
        sys.exit(1)
    return events


def parse_time(ts_str: str) -> datetime:
    """Parse timestamp into datetime object."""
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


async def post_batch(batch: list, api_url: str) -> None:
    """Post a batch of events to the ingestion endpoint."""
    async with httpx.AsyncClient() as client:
        try:
            url = f"{api_url.rstrip('/')}/api/v1/events/ingest"
            resp = await client.post(url, json=batch, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                print(
                    f"Posted {len(batch)} events: Accepted={data.get('accepted')}, Duplicates={data.get('duplicates')}"
                )
            else:
                print(f"Failed to post batch: HTTP {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Exception during post batch: {e}")


async def replay_events(path: str, speed: float, api_url: str, batch_size: int = 50) -> None:
    """Replay events sorting by timestamp and sleeping according to relative intervals."""
    events = load_jsonl(path)
    if not events:
        print("No events found in file.")
        return

    # Sort to ensure realistic chronological ordering
    events.sort(key=lambda e: e["timestamp"])
    print(f"Replaying {len(events)} events at {speed}x speed to {api_url}...")

    prev_ts = parse_time(events[0]["timestamp"])
    batch = []

    for event in events:
        curr_ts = parse_time(event["timestamp"])
        gap = (curr_ts - prev_ts).total_seconds()

        # When gap occurs and we have a batch, send it and sleep
        if gap > 0 and len(batch) >= batch_size:
            await post_batch(batch, api_url)
            batch.clear()
            await asyncio.sleep(gap / speed)

        batch.append(event)
        prev_ts = curr_ts

    if batch:
        await post_batch(batch, api_url)

    print("Replay complete ✅")

    # Write to log.txt
    try:
        with open("log.txt", "a", encoding="utf-8") as lf:
            lf.write(
                f"[{datetime.now().isoformat()}] REPLAY: replayed {len(events)} events from {path} at {speed}x speed to {api_url}.\n"
            )
    except Exception as e:
        print(f"[WARN] Failed to write to log.txt: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay events JSONL into API")
    parser.add_argument("--jsonl", required=True, help="Path to events JSONL file")
    parser.add_argument("--speed", type=float, default=5.0, help="Replay speed multiplier")
    parser.add_argument(
        "--api-url", default="http://localhost:8000", help="FastAPI Server Root URL"
    )
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for posts")
    args = parser.parse_args()

    asyncio.run(replay_events(args.jsonl, args.speed, args.api_url, args.batch_size))
