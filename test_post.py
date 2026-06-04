import asyncio
import json

import httpx


async def test():
    data = []
    with open("tests/fixtures/group_entry.jsonl") as f:
        for line in f:
            if line.strip() and not line.startswith("//"):
                data.append(json.loads(line))

    resp = await httpx.AsyncClient().post("http://localhost:8000/api/v1/events/ingest", json=data)
    print(resp.json())


asyncio.run(test())
