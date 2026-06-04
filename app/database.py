"""
app/database.py — Async database setup (PostgreSQL primary, SQLite fallback)
Purplle Store Intelligence API
"""

import contextlib
import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.settings import settings

DATABASE_URL = os.getenv("DATABASE_URL", settings.database_url)

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)


async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    """FastAPI dependency: yields an async DB session."""
    async with async_session_maker() as session:
        yield session


@contextlib.asynccontextmanager
async def get_session_context():
    async with async_session_maker() as session:
        yield session
