"""Centralized application settings and configuration management via Pydantic."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core App & Environment Isolation
    app_name: str = "IT Network Support AI Agent"
    app_env: str = "development"
    env_slug: str = "dev"
    debug: bool = False
    log_level: str = "INFO"
    cors_origin_list: list[str] = ["*"]
    secret_key: str = "it-net-default-insecure-secret-key-replace-in-production"
    encryption_key: str = "it-net-default-crypto-key-32-ch!"

    # Initial Super Admin Bootstrap
    admin_username: str = "admin"
    admin_password: str = "it-net-admin-change-me"
    admin_email: Optional[str] = "admin@kazyon.com"
    admin_display_name: str = "Network Support Super Admin"
    auth_token_expire_hours: int = 24

    # Database (SQLite local fallback; PostgreSQL 16 in dev/prod containers)
    database_url: str = "sqlite+aiosqlite:///./data/it_net_support.db"
    sync_database_url: str = "sqlite:///./data/it_net_support.db"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_sec: int = 1800

    # Redis 7 (Cache, Distributed Locks & Task Coordination)
    redis_url: str = "redis://localhost:6385/0"
    cache_enabled: bool = True
    cache_default_ttl_sec: int = 120

    # Self-Hosted vLLM AI Server (Gemma 4 26B A4B NVFP4 on 10.100.109.9:8002)
    vllm_base_url: str = "http://10.100.109.9:8002"
    vllm_api_key: Optional[str] = None
    default_worker_model: str = "google/gemma-4-26B-A4B-it"
    default_router_model: str = "google/gemma-4-26B-A4B-it"
    vllm_max_tokens: int = 1024
    vllm_temperature: float = 0.2
    vllm_pool_max_connections: int = 32
    vllm_pool_max_keepalive: int = 16
    vllm_pool_keepalive_expiry_sec: float = 300.0

    # Inbound / Outbound Email Engine (Branch & ISP Communication)
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_use_ssl: bool = True
    imap_folder: str = "INBOX"
    imap_poll_interval_sec: int = 60

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_address: str = "network-support@kazyon.com"
    max_outbound_emails_per_ticket_hour: int = 6

    # Troubleshooting Script Executor & ISP Follow-up Scheduler
    diagnostic_timeout_sec: int = 60
    default_isp_followup_interval_min: int = 60
    default_timezone: str = "Africa/Cairo"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
