"""
app/worker.py — Redis stream consumer for events
Reads events from Redis Stream and persists them to the database using SQLModel.
"""

import asyncio
from datetime import datetime

import redis.asyncio as redis
import structlog
from sqlmodel import select

from app.core.settings import settings
from app.database import get_session_context
from app.models import EventDB, VisitorSessionDB
from app.websocket import manager

log = structlog.get_logger()

STREAM_NAME = "events_stream"
CONSUMER_GROUP = "sqlite_workers"
CONSUMER_NAME = "worker_1"

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def init_redis_group():
    try:
        await redis_client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        log.info("redis.group_created", group=CONSUMER_GROUP)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP Consumer Group name already exists" not in str(e):
            log.error("redis.group_create_error", error=str(e))


async def process_event(event_data: dict, session):
    try:
        event_id = event_data["event_id"]
        # Idempotency check
        result = await session.execute(select(EventDB).where(EventDB.event_id == event_id))
        if result.scalar_one_or_none() is not None:
            return  # Duplicate

        ts = datetime.fromisoformat(event_data["timestamp"].replace("Z", "+00:00"))
        is_staff = event_data.get("is_staff") in (True, "True")

        db_event = EventDB(
            event_id=event_id,
            store_id=event_data["store_id"],
            camera_id=event_data["camera_id"],
            visitor_id=event_data["visitor_id"],
            event_type=event_data["event_type"],
            timestamp=ts,
            zone_id=event_data.get("zone_id"),
            dwell_ms=int(event_data.get("dwell_ms", 0)),
            is_staff=is_staff,
            confidence=float(event_data.get("confidence", 0.9)),
            metadata_json=event_data.get("metadata", "{}"),
        )
        session.add(db_event)

        # Update Visitor Sessions
        visitor_id = event_data["visitor_id"]
        store_id = event_data["store_id"]
        event_type = event_data["event_type"]

        sess_res = await session.execute(
            select(VisitorSessionDB).where(
                VisitorSessionDB.visitor_id == visitor_id,
                VisitorSessionDB.store_id == store_id,
            )
        )
        visitor_sess = sess_res.scalar_one_or_none()

        if event_type in ("ENTRY", "REENTRY"):
            if visitor_sess is None:
                visitor_sess = VisitorSessionDB(
                    store_id=store_id,
                    visitor_id=visitor_id,
                    is_staff=is_staff,
                    started_at=ts,
                    converted=False,
                )
                session.add(visitor_sess)
        elif event_type == "BILLING_QUEUE_JOIN":
            if visitor_sess is None:
                visitor_sess = VisitorSessionDB(
                    store_id=store_id,
                    visitor_id=visitor_id,
                    is_staff=is_staff,
                    started_at=ts,
                    converted=True,
                )
                session.add(visitor_sess)
            else:
                visitor_sess.converted = True
        elif event_type == "BILLING_QUEUE_ABANDON" and visitor_sess is not None:
            visitor_sess.converted = False
            session.add(visitor_sess)

        await session.commit()

        # Broadcast via websocket
        await manager.broadcast({"type": "new_event", "event": event_data})
    except Exception as e:
        log.error("worker.process_error", error=str(e), event_id=event_data.get("event_id"))
        await session.rollback()


async def consume_stream():
    await init_redis_group()
    log.info("worker.started", stream=STREAM_NAME)
    while True:
        try:
            # Read from stream
            messages = await redis_client.xreadgroup(
                CONSUMER_GROUP, CONSUMER_NAME, {STREAM_NAME: ">"}, count=10, block=2000
            )

            if not messages:
                continue

            for _stream, msgs in messages:
                async with get_session_context() as session:
                    for message_id, event_data in msgs:
                        await process_event(event_data, session)
                        # Acknowledge the message
                        await redis_client.xack(STREAM_NAME, CONSUMER_GROUP, message_id)
        except Exception as e:
            log.error("worker.loop_error", error=str(e))
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(consume_stream())
