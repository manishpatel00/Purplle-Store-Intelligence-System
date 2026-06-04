"""
app/models.py — SQLModel event schema for Purplle Store Intelligence
"""

import json
from datetime import datetime

from sqlalchemy import Index, text
from pydantic import field_validator
from sqlmodel import Field, SQLModel


class EventDB(SQLModel, table=True):
    """
    Database model for store events.
    event_id is the deduplication key (idempotent ingest).
    metadata_json stores queue_depth, sku_zone, session_seq as JSON string.
    """

    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(unique=True, index=True)  # UUID — dedup key
    store_id: str = Field(index=True)
    camera_id: str
    visitor_id: str = Field(index=True)
    event_type: str = Field(index=True)
    timestamp: datetime = Field(index=True)
    zone_id: str | None = Field(default=None, index=True)
    dwell_ms: int = Field(default=0)
    is_staff: bool = Field(default=False)
    confidence: float = Field(default=0.9)
    metadata_json: str = Field(default="{}")  # JSON string

    def get_metadata(self) -> dict:
        """Parse metadata_json safely."""
        try:
            return json.loads(self.metadata_json)
        except Exception:
            return {}

    __table_args__ = (
        Index(
            "idx_customer_events",
            "store_id",
            "timestamp",
            "event_type",
            postgresql_where=text("is_staff = FALSE"),
            sqlite_where=text("is_staff = 0"),
        ),
    )


class VisitorSessionDB(SQLModel, table=True):
    """
    Database model for visitor sessions.
    Speeds up analytics queries by avoiding full scans of the events table.
    """

    __tablename__ = "visitor_sessions"

    id: int | None = Field(default=None, primary_key=True)
    store_id: str = Field(index=True)
    visitor_id: str = Field(index=True)
    is_staff: bool = Field(default=False, index=True)
    started_at: datetime = Field(index=True)
    converted: bool = Field(default=False, index=True)

    __table_args__ = (
        Index(
            "idx_customer_sessions",
            "store_id",
            "started_at",
            postgresql_where=text("is_staff = FALSE"),
            sqlite_where=text("is_staff = 0"),
        ),
        Index(
            "idx_anomaly_conversion",
            "store_id",
            "started_at",
            "converted",
            postgresql_where=text("is_staff = FALSE"),
            sqlite_where=text("is_staff = 0"),
        ),
    )


class EventCreate(SQLModel):
    """
    Pydantic model for incoming event payload from pipeline.
    Accepts both Z-suffix and offset-aware ISO-8601 timestamps.
    """

    event_id: str
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: str
    zone_id: str | None = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = 0.9
    extra_metadata: dict = Field(default_factory=dict)



    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"event_id must be a valid UUID: {v}")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("Timestamp must be ISO-8601 UTC with Z suffix")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event type: {v}")
        return v

    @field_validator("extra_metadata")
    @classmethod
    def validate_metadata(cls, v: dict) -> dict:
        qd = v.get("queue_depth")
        if qd is not None and isinstance(qd, (int, float)) and qd < 0:
            raise ValueError("queue_depth must be non-negative")
        return v

# Valid event types
VALID_EVENT_TYPES = frozenset(
    {
        "ENTRY",
        "EXIT",
        "REENTRY",
        "ZONE_ENTER",
        "ZONE_EXIT",
        "ZONE_DWELL",
        "BILLING_QUEUE_JOIN",
        "BILLING_QUEUE_ABANDON",
        "PURCHASE_MATCHED",
    }
)
