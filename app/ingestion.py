"""
app/ingestion.py — POST /events/ingest with idempotent deduplication and session updates
Purplle Store Intelligence API
"""

import json
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import ValidationError

from app.database import get_session
from app.models import VALID_EVENT_TYPES, EventCreate, EventDB, VisitorSessionDB
from app.websocket import manager

log = structlog.get_logger()
router = APIRouter(tags=["events"])

MAX_BATCH_SIZE = 500


@router.post("/events/ingest")
async def ingest_events(
    events: list[dict[str, Any]],
    response: Response,
    session: AsyncSession = Depends(get_session)
):
    """
    Bulk ingest store events from the detection pipeline.
    Validates, deduplicates, and persists to both events and visitor_sessions tables.
    """
    if len(events) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Batch too large: {len(events)} > max {MAX_BATCH_SIZE}",
        )

    accepted_ids: list[str] = []
    rejected: list[dict] = []
    duplicates: list[str] = []

    for raw_event in events:
        try:
            # Validate via Pydantic model manually to allow partial batch success
            try:
                event = EventCreate(**raw_event)
            except ValidationError as ve:
                rejected.append(
                    {
                        "event_id": raw_event.get("event_id"),
                        "reason": str(ve),
                    }
                )
                continue

            try:
                ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError as e:
                rejected.append(
                    {
                        "event_id": event.event_id,
                        "reason": f"invalid timestamp: {e}",
                    }
                )
                continue

            # Check for duplicate by event_id (idempotency)
            existing = await session.execute(
                select(EventDB).where(EventDB.event_id == event.event_id)
            )
            if existing.scalar_one_or_none() is not None:
                duplicates.append(event.event_id)
                continue

            # Persist Event
            metadata_str = json.dumps(event.extra_metadata or {})
            db_event = EventDB(
                event_id=event.event_id,
                store_id=event.store_id,
                camera_id=event.camera_id,
                visitor_id=event.visitor_id,
                event_type=event.event_type,
                timestamp=ts,
                zone_id=event.zone_id,
                dwell_ms=event.dwell_ms,
                is_staff=event.is_staff,
                confidence=event.confidence,
                metadata_json=metadata_str,
            )
            session.add(db_event)

            # Persist/Update Visitor Session
            visitor_id = event.visitor_id
            store_id = event.store_id
            is_staff = event.is_staff

            # Check if session exists
            sess_res = await session.execute(
                select(VisitorSessionDB).where(
                    VisitorSessionDB.visitor_id == visitor_id,
                    VisitorSessionDB.store_id == store_id,
                )
            )
            visitor_sess = sess_res.scalar_one_or_none()

            if event.event_type in ("ENTRY", "REENTRY"):
                if visitor_sess is None:
                    visitor_sess = VisitorSessionDB(
                        store_id=store_id,
                        visitor_id=visitor_id,
                        is_staff=is_staff,
                        started_at=ts,
                        converted=False,
                    )
                    session.add(visitor_sess)
            elif event.event_type == "BILLING_QUEUE_JOIN":
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
                    session.add(visitor_sess)
            elif event.event_type == "BILLING_QUEUE_ABANDON" and visitor_sess is not None:
                visitor_sess.converted = False
                session.add(visitor_sess)

            accepted_ids.append(event.event_id)

            # Broadcast via websocket
            await manager.broadcast(
                {
                    "type": "new_event",
                    "event": {
                        "event_id": event.event_id,
                        "store_id": event.store_id,
                        "camera_id": event.camera_id,
                        "visitor_id": event.visitor_id,
                        "event_type": event.event_type,
                        "timestamp": event.timestamp,
                        "zone_id": event.zone_id,
                        "dwell_ms": event.dwell_ms,
                        "is_staff": event.is_staff,
                        "confidence": event.confidence,
                        "metadata": event.extra_metadata or {},
                    },
                }
            )

        except Exception as e:
            rejected.append({"event_id": raw_event.get("event_id"), "reason": str(e)})

    if accepted_ids:
        await session.commit()
        
    if not accepted_ids and rejected:
        raise HTTPException(status_code=400, detail=rejected)
    elif rejected:
        response.status_code = status.HTTP_207_MULTI_STATUS

    log.info(
        "events.ingested",
        accepted=len(accepted_ids),
        rejected=len(rejected),
        duplicates=len(duplicates),
        total=len(events),
    )

    return {
        "accepted": len(accepted_ids),
        "rejected": rejected,
        "duplicates": len(duplicates),
        "total_received": len(events),
    }
