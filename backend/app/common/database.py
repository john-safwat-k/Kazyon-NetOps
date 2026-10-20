"""SQLAlchemy database engine, sessionmaker, and portable JSONVariant base."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

_is_sqlite = "sqlite" in settings.sync_database_url

if _is_sqlite:
    Path("./data").mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        settings.sync_database_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    engine = create_engine(
        settings.sync_database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle_sec,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

# Portable JSON column type: resolves to JSONB on PostgreSQL and JSON on SQLite.
JSONVariant: Any = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
