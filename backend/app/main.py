"""IT Network Support AI Agent & Ticketing Harness — Unified FastAPI Entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import app.auth.models  # noqa: F401
import app.directory.models  # noqa: F401
import app.ticketing.models  # noqa: F401
from app.agent.vllm_client import aclose_vllm_client, check_vllm_health
from app.auth.service import ensure_initial_admin
from app.common.config import get_settings
from app.common.database import Base, SessionLocal, engine
from app.common.exceptions import register_exception_handlers
from app.common.logging import configure_logging

configure_logging(level=get_settings().log_level)
logger = logging.getLogger("it_net.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    if settings.app_env.lower() == "production":
        insecure_placeholders = {
            "secret_key": {
                "it-net-default-insecure-secret-key-replace-in-production",
                "REPLACE_WITH_OPENSSL_RAND_HEX_32_IN_PROD",
            },
            "encryption_key": {
                "it-net-default-crypto-key-32-ch!",
                "REPLACE_WITH_32_BYTE_KEY_IN_PROD",
            },
            "admin_password": {
                "it-net-admin-change-me",
                "REPLACE_WITH_STRONG_ADMIN_PASSWORD_IN_PROD",
            },
        }
        for field, bad_values in insecure_placeholders.items():
            if getattr(settings, field) in bad_values:
                raise RuntimeError(
                    f"Production startup failure: '{field}' is still set to an insecure placeholder. "
                    "Configure actual credentials in .env before running in production."
                )

    if settings.app_env.lower() == "development" and "sqlite" in settings.sync_database_url:
        logger.info("Local SQLite dev bootstrap: creating any missing tables from models...")
        Base.metadata.create_all(bind=engine)
    else:
        logger.info(
            "Schema owned by Alembic (env=%s); run 'alembic upgrade head' at deploy.",
            settings.app_env,
        )

    db: Session = SessionLocal()
    try:
        ensure_initial_admin(db)
    finally:
        db.close()

    logger.info(
        "IT Network Support AI Agent (%s / %s) initialized. vLLM target: %s (%s)",
        settings.app_env,
        settings.env_slug,
        settings.vllm_base_url,
        settings.default_worker_model,
    )
    yield

    logger.info("Shutting down IT Network Support AI Agent...")
    await aclose_vllm_client()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="IT Network Support AI Agent & Ticketing Harness",
    version="1.0.0",
    description=(
        "Autonomous IT network support agent and Jira-style ticketing platform. "
        "Ingests branch emails, runs network diagnostics, escalates to ISPs, "
        "chases ISP updates, verifies fixes, and confirms resolution with branches."
    ),
    lifespan=lifespan,
)

register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    """Health check endpoint used by Docker Compose, deploy.sh, and the Ops Console."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "env_slug": settings.env_slug,
        "version": app.version,
        "vllm_base_url": settings.vllm_base_url,
        "vllm_model": settings.default_worker_model,
    }


@app.get("/api/v1/system/vllm-status")
async def vllm_status() -> dict[str, Any]:
    """Live connectivity check against Gemma 4 26B A4B on vLLM (10.100.109.9:8002)."""
    return await check_vllm_health()


# Mount compiled React SPA if frontend/dist exists
dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if dist_dir.exists() and (dist_dir / "index.html").exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        file_path = dist_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")
