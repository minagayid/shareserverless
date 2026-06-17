from __future__ import annotations

import logging

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging
from app.core.metrics import instrument_app
from app.api.v1 import router as api_v1_router


def create_app() -> FastAPI:
    configure_logging(settings.log_level)
    logger = structlog.get_logger("app.startup")

    application = FastAPI(
        title=settings.app_name,
        description="Scheduler, orchestration and governance API for ShareServerless.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    async def on_startup() -> None:
        init_db()
        logger.info("application_started", env=settings.app_env, debug=settings.debug)

    application.include_router(api_v1_router, prefix=settings.api_prefix)

    instrument_app(application)

    @application.get("/health")
    async def health() -> dict:
        return {"status": "ok", "env": settings.app_env}

    return application


app = create_app()
