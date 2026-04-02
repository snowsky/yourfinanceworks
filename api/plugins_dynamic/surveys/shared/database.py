"""
Self-contained database setup for yfw-surveys.

Works in both plugin and standalone mode. Configure via the
SURVEYS_DATABASE_URL environment variable (defaults to SQLite).
"""
from __future__ import annotations

import os
from typing import Generator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


def _get_url() -> str:
    return os.environ.get("SURVEYS_DATABASE_URL", "sqlite:///./surveys.db")


def _init_engine():
    global _engine, _SessionLocal
    if _engine is not None:
        return
    url = _get_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=connect_args)
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def create_tables():
    """Create all survey tables. Call once at startup."""
    _init_engine()
    # Import models so they register with Base
    try:
        from .models import surveys  # noqa: F401
    except (ImportError, ValueError):
        import shared.models.surveys  # noqa: F401
    Base.metadata.create_all(bind=_engine)


def get_db() -> Generator[Optional[Session], None, None]:
    """FastAPI dependency: yields a DB session."""
    _init_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
