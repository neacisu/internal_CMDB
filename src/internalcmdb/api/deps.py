"""FastAPI dependencies — database session and settings."""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings


def _make_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@lru_cache(maxsize=1)
def _get_session_factory() -> sessionmaker[Session]:
    """Return the module-level session factory, creating it once on first call."""
    return _make_sessionmaker(get_settings())


def get_db() -> Generator[Session]:
    """Yield a SQLAlchemy session; close on exit."""
    factory = _get_session_factory()
    db: Session = factory()
    try:
        yield db
    finally:
        db.close()
