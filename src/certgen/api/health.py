"""Healthcheck endpoint with database connectivity check."""

from fastapi import APIRouter, Depends

from certgen.api.deps import check_db_health

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check(_db_ok: bool = Depends(check_db_health)) -> dict[str, str]:
    """Health check endpoint confirming service and database operational status."""
    return {"status": "ok", "database": "connected"}
