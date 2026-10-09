"""Database setup, engine factory, pragmas, and session management."""

import sqlite3
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from certgen.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base."""

    pass


def setup_sqlite_pragmas(engine: Engine) -> None:
    """Register SQLite pragmas: WAL mode, foreign keys, and busy timeout."""

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, connection_record) -> None:
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()


def create_engine_from_url(database_url: str) -> Engine:
    """Create SQLAlchemy engine with appropriate settings for the dialect."""
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # If file-based SQLite, ensure directory exists
        if "///" in database_url and not database_url.startswith("sqlite:///:memory:"):
            db_path_str = database_url.split("///")[-1]
            db_path = Path(db_path_str).resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        database_url,
        connect_args=connect_args,
        echo=False,
    )

    if database_url.startswith("sqlite"):
        setup_sqlite_pragmas(engine)

    return engine


# Default application engine & sessionmaker using settings
settings = get_settings()
engine = create_engine_from_url(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(engine_instance: Engine | None = None) -> None:
    """Create all database tables."""
    target_engine = engine_instance or engine
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency yielding a database session per request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
