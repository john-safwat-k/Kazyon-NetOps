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

from app.agent.scheduler import (
    request_immediate_poll,
    start_background_email_loop,
    stop_background_email_loop,
)
from app.agent.vllm_client import aclose_vllm_client
from app.auth import models as _auth_models  # noqa: F401
from app.auth.router import auth_router, roles_router, users_router
from app.auth.service import ensure_initial_admin
from app.common import audit as _audit_models  # noqa: F401
from app.common.config import get_settings
from app.common.database import Base, SessionLocal, engine
from app.common.exceptions import register_exception_handlers
from app.common.logging import configure_logging
from app.diagnostics.router import diagnostics_router
from app.directory import models as _directory_models  # noqa: F401
from app.directory.router import branches_router, isps_router
from app.directory.service import ensure_directory_seeded
from app.email_engine.smtp_listener import start_inbound_smtp_listener, stop_inbound_smtp_listener
from app.ticketing import models as _ticketing_models  # noqa: F401
from app.ticketing.router import (
    dashboard_router,
    emails_router,
    escalations_router,
    replication_router,
    settings_router,
    tickets_router,
    ws_router,
)
from app.ticketing.service import ensure_operational_seed_data, purge_legacy_demo_data

configure_logging(level=get_settings().log_level)
logger = logging.getLogger("it_net.main")


def _ensure_sqlite_dev_columns() -> None:
    """Ensure any newly added v5.0 columns exist when running against an older local SQLite file."""
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    inspector = sa_inspect(engine)
    existing_tables = set(inspector.get_table_names())
    # If ticket_emails.ticket_id or diagnostic_runs.ticket_id is still NOT NULL from v1, drop and recreate
    for tbl in ("ticket_emails", "diagnostic_runs"):
        if tbl in existing_tables:
            reflected_cols = {c["name"]: c for c in inspector.get_columns(tbl)}
            if "ticket_id" in reflected_cols and not reflected_cols["ticket_id"].get(
                "nullable", True
            ):
                with engine.begin() as conn:
                    conn.execute(text(f"DROP TABLE IF EXISTS {tbl}"))
                Base.metadata.create_all(bind=engine)
                inspector = sa_inspect(engine)
                existing_tables = set(inspector.get_table_names())
    alter_map: dict[str, list[tuple[str, str]]] = {
        "users": [("last_login_at", "TIMESTAMP")],
        "network_providers": [
            ("four_g_hub_ip", "VARCHAR(128)"),
            ("welcome_sla_minutes", "INTEGER DEFAULT 120"),
            ("followup_sla_minutes", "INTEGER DEFAULT 300"),
        ],
        "branches": [
            ("ip_1", "VARCHAR(128) DEFAULT '10.0.0.1'"),
            ("ip_2", "VARCHAR(128) DEFAULT '10.0.0.2'"),
            ("isp_name", "VARCHAR(64) DEFAULT 'NOOR'"),
            ("isp_contact_mail", "VARCHAR(255) DEFAULT 'noc@noor.net'"),
            ("regional_it_email", "VARCHAR(255)"),
            ("four_g_hub_ip", "VARCHAR(128)"),
            ("ll_circuit_id", "VARCHAR(128)"),
            ("backup_circuit_id", "VARCHAR(128)"),
        ],
        "tickets": [
            ("trigger_source", "VARCHAR(48) DEFAULT 'DIRECT_EMAIL'"),
            ("sender_email", "VARCHAR(255)"),
            ("site_contact_phone", "VARCHAR(64)"),
            ("router_image_paths", "JSON DEFAULT '[]'"),
            ("image_check_passed", "BOOLEAN"),
            ("image_analysis_summary", "TEXT"),
            ("connection_failure_type", "VARCHAR(64)"),
            ("isp_welcome_received", "BOOLEAN DEFAULT 0"),
            ("escalation_reason", "VARCHAR(64)"),
            ("human_escalated_to", "VARCHAR(255)"),
        ],
        "diagnostic_runs": [
            ("branch_code", "VARCHAR(64)"),
            ("ip_1_up", "BOOLEAN"),
            ("ip_2_up", "BOOLEAN"),
            ("four_g_hub_detected", "BOOLEAN"),
            ("detected_hub_ip", "VARCHAR(128)"),
            ("diagnosis_code", "VARCHAR(64)"),
        ],
        "ticket_emails": [
            ("attachments_json", "JSON DEFAULT '[]'"),
            ("raw_headers", "JSON DEFAULT '{}'"),
            ("classification_label", "VARCHAR(64)"),
        ],
        "system_settings": [
            ("smtp_security", "VARCHAR(16) NOT NULL DEFAULT 'starttls'"),
            ("smtp_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
            ("imap_use_ssl", "BOOLEAN NOT NULL DEFAULT 1"),
            ("imap_folder", "VARCHAR(128) NOT NULL DEFAULT 'INBOX'"),
            ("imap_username", "VARCHAR(255) NOT NULL DEFAULT ''"),
            ("imap_password_encrypted", "TEXT NOT NULL DEFAULT ''"),
            ("smtp_username", "VARCHAR(255) NOT NULL DEFAULT ''"),
            ("smtp_password_encrypted", "TEXT NOT NULL DEFAULT ''"),
            ("test_redirect_email", "VARCHAR(255) NOT NULL DEFAULT ''"),
        ],
    }
    with engine.begin() as conn:
        for table_name, cols in alter_map.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            for col_name, col_def in cols:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))


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
        _ensure_sqlite_dev_columns()
    else:
        logger.info(
            "Schema owned by Alembic (env=%s); run 'alembic upgrade head' at deploy.",
            settings.app_env,
        )

    db: Session = SessionLocal()
    try:
        ensure_initial_admin(db)
        ensure_directory_seeded(db)
        purge_legacy_demo_data(db)
        ensure_operational_seed_data(db)
    finally:
        db.close()

    logger.info(
        "IT Network Support AI Agent (%s / %s) initialized. vLLM target: %s (%s)",
        settings.app_env,
        settings.env_slug,
        settings.vllm_base_url,
        settings.default_worker_model,
    )
    start_background_email_loop()
    await start_inbound_smtp_listener(on_message_stored=request_immediate_poll)
    yield

    logger.info("Shutting down IT Network Support AI Agent...")
    await stop_inbound_smtp_listener()
    await stop_background_email_loop()
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

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(branches_router)
app.include_router(isps_router)
app.include_router(diagnostics_router)
app.include_router(dashboard_router)
app.include_router(tickets_router)
app.include_router(replication_router)
app.include_router(escalations_router)
app.include_router(emails_router)
app.include_router(settings_router)
app.include_router(ws_router)


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
