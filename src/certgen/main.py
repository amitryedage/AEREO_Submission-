"""FastAPI application entrypoint for Bulk Certificate Generator."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from certgen.api.health import router as health_router
from certgen.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown events."""
    # Initialize database tables
    init_db()
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

    # Register routers
    application.include_router(health_router)

    return application


app = create_app()
