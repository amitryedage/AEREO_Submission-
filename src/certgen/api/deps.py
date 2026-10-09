"""FastAPI dependencies and service collaborators."""

from functools import lru_cache

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from certgen.config import Settings, get_settings
from certgen.db import SessionLocal, get_db
from certgen.rendering.base import CertificateRenderer
from certgen.rendering.pdf_renderer import ReportLabCertificateRenderer
from certgen.storage.local import FileStorage, LocalFileStorage

__all__ = [
    "get_db",
    "get_settings",
    "check_db_health",
    "get_renderer",
    "get_storage",
    "get_session_factory",
]


def check_db_health(db: Session = Depends(get_db)) -> bool:
    """Verify database connection is operational."""
    db.execute(text("SELECT 1"))
    return True


@lru_cache
def get_renderer() -> CertificateRenderer:
    """Dependency returning the certificate PDF renderer."""
    return ReportLabCertificateRenderer()


def get_storage(settings: Settings = Depends(get_settings)) -> FileStorage:
    """Dependency returning the file storage implementation."""
    return LocalFileStorage(settings.storage_dir)


def get_session_factory() -> sessionmaker[Session]:
    """Dependency returning the SQLAlchemy session factory for background workers."""
    return SessionLocal
