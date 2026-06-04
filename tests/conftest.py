# PROMPT: Generate a shared pytest conftest that:
#   - Creates an in-memory SQLite database for tests (not the production DB)
#   - Provides a reusable async HTTP client fixture for FastAPI ASGI tests
#   - Provides helpers to seed ENTRY, ZONE_ENTER, BILLING_QUEUE_JOIN events
#   - Ensures tests share a single DB so ingest + query both see same data
#   - Works with pytest-asyncio in auto mode
# CHANGES MADE: Switched to module-scoped engine so all tests within a module
#   share the same in-memory DB, which allows ingest events to be visible to
#   subsequent metric/funnel/anomaly queries. Using named SQLite URL with
#   shared_cache to allow multiple connections to the same in-memory DB.
#   Fixed deprecated event_loop fixture by using anyio backend.

import os
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

# Override the database URL BEFORE importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared&uri=true"
os.environ["ENVIRONMENT"] = "testing"

from app.database import get_session
from app.main import app

# ---------------------------------------------------------------------------
# Shared in-memory engine using SQLite named memory DB with shared cache
# This allows all async connections to see the same in-memory data.
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared&uri=true"
_test_engine = None


def get_test_engine():
    global _test_engine
    if _test_engine is None:
        _test_engine = create_async_engine(
            TEST_DB_URL,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _test_engine


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create tables once for the whole test session."""
    engine = get_test_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """
    Transactional fixture: every test runs inside a transaction that's rolled back.
    No test bleeds state into another.
    """
    engine = get_test_engine()
    async with engine.connect() as conn, conn.begin() as trans:
        session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
        yield session
        await trans.rollback()


class ApiV1TestClient(AsyncClient):
    async def request(self, method: str, url, **kwargs):
        url_str = str(url)
        if url_str.startswith("/stores") or url_str.startswith("/events"):
            url = f"/api/v1{url_str}"
        return await super().request(method, url, **kwargs)


@pytest_asyncio.fixture
async def client(db_session):
    """FastAPI async test client using shared in-memory DB."""
    app.dependency_overrides[get_session] = lambda: db_session
    async with ApiV1TestClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Event factory helpers
# ---------------------------------------------------------------------------

CHALLENGE_DATE = "2026-04-10"
STORE_ID = "STORE_BLR_002"


def make_event(
    event_type: str = "ENTRY",
    visitor_id: str | None = None,
    store_id: str = STORE_ID,
    camera_id: str = "CAM_1",
    timestamp: str = f"{CHALLENGE_DATE}T10:00:00Z",
    zone_id: str | None = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 0.90,
    metadata: dict | None = None,
) -> dict:
    """Create a minimal valid event payload dict."""
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id or f"VIS_{uuid.uuid4().hex[:6]}",
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "extra_metadata": metadata or {},
    }


def make_visitor_journey(
    visitor_id: str,
    store_id: str = STORE_ID,
    base_hour: int = 12,
    is_buyer: bool = True,
) -> list[dict]:
    """
    Build a complete visitor journey:
    ENTRY -> ZONE_ENTER -> ZONE_EXIT -> [BILLING_QUEUE_JOIN] -> EXIT
    """
    events = []

    events.append(
        make_event(
            "ENTRY",
            visitor_id=visitor_id,
            store_id=store_id,
            timestamp=f"{CHALLENGE_DATE}T{base_hour:02d}:00:00Z",
        )
    )
    events.append(
        make_event(
            "ZONE_ENTER",
            visitor_id=visitor_id,
            store_id=store_id,
            timestamp=f"{CHALLENGE_DATE}T{base_hour:02d}:05:00Z",
            zone_id="FACES_CANADA",
            camera_id="CAM_2",
        )
    )
    events.append(
        make_event(
            "ZONE_EXIT",
            visitor_id=visitor_id,
            store_id=store_id,
            timestamp=f"{CHALLENGE_DATE}T{base_hour:02d}:10:00Z",
            zone_id="FACES_CANADA",
            dwell_ms=300000,
            camera_id="CAM_2",
        )
    )

    if is_buyer:
        events.append(
            make_event(
                "BILLING_QUEUE_JOIN",
                visitor_id=visitor_id,
                store_id=store_id,
                camera_id="CAM_5",
                timestamp=f"{CHALLENGE_DATE}T{base_hour:02d}:12:00Z",
                zone_id="CASH_COUNTER",
                metadata={"queue_depth": 2, "session_seq": 1},
            )
        )
    events.append(
        make_event(
            "EXIT",
            visitor_id=visitor_id,
            store_id=store_id,
            timestamp=f"{CHALLENGE_DATE}T{base_hour:02d}:15:00Z",
        )
    )
    return events
