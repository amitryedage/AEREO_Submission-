"""FastAPI application entrypoint for Bulk Certificate Generator."""

from fastapi import FastAPI

from certgen.api.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="Bulk Certificate Generator API",
        description="High-throughput bulk certificate generation backend API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Register routers
    application.include_router(health_router)

    return application


app = create_app()
