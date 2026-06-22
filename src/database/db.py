"""
CyberLens — Database Engine & Session Management
====================================================
SQLite engine setup with session management and initialization.
"""

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Officer

logger = logging.getLogger("cyberlens.database")

# Default database path
DEFAULT_DB_PATH = Path("data/cyberlens.db")


def get_database_url(db_path: str = None) -> str:
    """Get SQLite database URL.

    Args:
        db_path: Optional custom database file path.

    Returns:
        SQLAlchemy database URL string.
    """
    if db_path:
        return f"sqlite:///{db_path}"

    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    return f"sqlite:///{DEFAULT_DB_PATH}"


# Create engine (lazy — only created once)
_engine = None
_SessionLocal = None


def _get_engine(db_url: str = None):
    """Get or create the SQLAlchemy engine."""
    global _engine, _SessionLocal

    if _engine is None or db_url:
        url = db_url or get_database_url()
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},  # SQLite needs this
            pool_pre_ping=True,
        )

        # Enable WAL mode for better concurrent performance
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_engine,
        )
        logger.info("Database engine created: %s", url)

    return _engine


def init_db(db_url: str = None) -> None:
    """Initialize database — create tables and seed default data.

    Args:
        db_url: Optional custom database URL.
    """
    engine = _get_engine(db_url)

    # Ensure data directory exists
    if "sqlite" in str(engine.url):
        db_file = str(engine.url).replace("sqlite:///", "")
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)

    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    # Seed default officer
    _seed_default_officer()


def _seed_default_officer() -> None:
    """Seed a default officer if none exists."""
    with get_session() as session:
        existing = session.query(Officer).first()
        if not existing:
            default_officer = Officer(
                name="Inspector Cyber Cell",
                badge_number="GGN-CC-001",
                station="Gurugram Cyber Cell",
                rank="Inspector",
            )
            session.add(default_officer)
            session.commit()
            logger.info("Seeded default officer: %s", default_officer)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for database sessions.

    Yields:
        SQLAlchemy Session instance.

    Usage:
        with get_session() as session:
            cases = session.query(Case).all()
    """
    engine = _get_engine()
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session.

    Yields:
        SQLAlchemy Session instance.
    """
    engine = _get_engine()
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_test_engine():
    """Create an in-memory SQLite engine for testing.

    Returns:
        Tuple of (engine, SessionLocal).
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    return engine, TestSession
