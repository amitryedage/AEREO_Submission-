"""FastAPI application entrypoint for Bulk Certificate Generator."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from certgen.api.certificates import router as certificates_router
from certgen.api.deps import get_renderer, get_storage
from certgen.api.health import router as health_router
from certgen.api.jobs import router as jobs_router
from certgen.config import Settings, get_settings
from certgen.db import SessionLocal, init_db
from certgen.errors import (
    AppError,
    app_error_handler,
    unhandled_exception_handler,
    validation_error_handler,
)
from certgen.models import Job, JobStatus
from certgen.services.processor import JobProcessor

logger = logging.getLogger("certgen.main")


def recover_interrupted_jobs(settings: Settings) -> None:
    """Recover and complete any jobs left in queued or processing status upon startup."""
    session = SessionLocal()
    try:
        interrupted = (
            session.query(Job)
            .filter(Job.status.in_([JobStatus.QUEUED.value, JobStatus.PROCESSING.value]))
            .all()
        )
        if interrupted:
            logger.info("Found %d interrupted jobs to recover on startup", len(interrupted))
            renderer = get_renderer()
            storage = get_storage(settings)
            processor = JobProcessor(
                session_factory=SessionLocal,
                renderer=renderer,
                storage=storage,
            )
            for job in interrupted:
                logger.info("Recovering job %s", job.id)
                processor.run(job.id)
    except Exception:
        logger.exception("Error during startup job recovery")
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    # 1. Initialize database tables
    init_db()

    # 2. Run startup job recovery unless disabled
    settings = get_settings()
    if not settings.disable_recovery:
        recover_interrupted_jobs(settings)

    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="Bulk Certificate Generator API",
        description="High-throughput bulk certificate generation backend API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Register error handlers
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(
        RequestValidationError,
        validation_error_handler,  # type: ignore[arg-type]
    )
    application.add_exception_handler(Exception, unhandled_exception_handler)

    # Register routers
    application.include_router(health_router)
    application.include_router(jobs_router)
    application.include_router(certificates_router)

    # Mount static assets directory for web UI
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        application.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return application


app = create_app()
