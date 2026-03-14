"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import (
    agent,
    dashboard,
    discovery,
    documents,
    governance,
    registry,
    results,
    retrieval,
    workers,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hook — nothing to initialise yet beyond eager config load."""
    get_settings()  # validates .env on startup
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    fapp = FastAPI(
        title="internalCMDB API",
        description=(
            "Enterprise infrastructure registry, discovery, governance and worker management API."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    fapp.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = "/api/v1"
    fapp.include_router(registry.router, prefix=prefix)
    fapp.include_router(discovery.router, prefix=prefix)
    fapp.include_router(governance.router, prefix=prefix)
    fapp.include_router(retrieval.router, prefix=prefix)
    fapp.include_router(agent.router, prefix=prefix)
    fapp.include_router(dashboard.router, prefix=prefix)
    fapp.include_router(workers.router, prefix=prefix)
    fapp.include_router(results.router, prefix=prefix)
    fapp.include_router(documents.router, prefix=prefix)

    @fapp.get("/health", tags=["meta"])
    def health() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok", "log_level": settings.log_level}

    return fapp


app = create_app()
