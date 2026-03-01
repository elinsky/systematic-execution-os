"""FastAPI application factory and startup/shutdown lifecycle."""

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sidecar.database import create_all_tables
from sidecar.utils.logging import configure_logging

logger = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="BAM Systematic Execution OS",
        description="Sidecar service for cross-project intelligence, automation, and query API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def on_startup() -> None:
        logger.info("startup_begin")
        await create_all_tables()
        logger.info("startup_complete", db="tables_ready")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        logger.info("shutdown")

    # Mount routers
    from sidecar.api.router import router  # noqa: E402
    app.include_router(router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
