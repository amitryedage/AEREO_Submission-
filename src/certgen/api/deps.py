"""FastAPI dependencies."""

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from certgen.config import get_settings
from certgen.db import get_db

__all__ = ["get_db", "get_settings", "check_db_health"]


def check_db_health(db: Session = Depends(get_db)) -> bool:
    """Verify database connection is operational."""
    db.execute(text("SELECT 1"))
    return True
