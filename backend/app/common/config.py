"""Centralized application settings and configuration management via Pydantic."""

from __future__ import annotations

from functools import lru_cache
from ipaddress import IPv4Network, IPv6Network, ip_network
from typing import Literal, Optional

from pydantic import model_validator
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
    # Seed values only: the endpoint, temperature and max tokens in use are the Page 12 settings
    vllm_max_tokens: int = 1024
    vllm_temperature: float = 0.2
    vllm_pool_max_connections: int = 32
    vllm_pool_max_keepalive: int = 16
    vllm_pool_keepalive_expiry_sec: float = 300.0
    llm_max_retries: int = 3
    llm_request_timeout_sec: float = 30.0
    # Inbound mail deferred because vLLM was down is re-ingested from this queue after the backoff
    llm_retry_queue_dir: str = "./data/imports/llm_retry"
    llm_retry_backoff_sec: int = 300

    # Outbound / Inbound SMTP Email Engine (Branch & ISP Communication)
    attachments_dir: str = "./data/attachments"

    # SMTP host, port, security mode, sender address and the on/off switch live in
    # `system_settings` (Page 12), with fallback to `SMTP_USERNAME` / `SMTP_PASSWORD` in `.env`.
    smtp_username: str = ""
    smtp_password: str = ""

    # Inbound SMTP listener: the company mail server forwards branch / ISP mail straight to the
    # agent. Accepted messages are written to the inbound dropbox and ingested by the poller.
    smtp_listener_enabled: bool = False
    smtp_listener_host: str = "0.0.0.0"
    smtp_listener_port: int = 2525
    # Comma-separated IPs / CIDRs allowed to connect (the forwarding mail server only)
    smtp_listener_allowed_clients: str = "127.0.0.1/32"
    # Comma-separated accepted recipients; empty = the Page 12 sender address only
    smtp_listener_allowed_recipients: str = ""
    smtp_listener_max_message_mb: int = 25
    smtp_listener_hostname: str = "netops-agent.kazyon.local"
    max_outbound_emails_per_ticket_hour: int = 6
    loop_guard_fail_open_for_tests: bool = False

    # Troubleshooting Script Executor & ISP Follow-up Scheduler
    diagnostic_mode: Literal["live", "simulated"] = "live"
    diagnostic_timeout_sec: int = 60
    default_isp_followup_interval_min: int = 60
    default_timezone: str = "Africa/Cairo"

    @model_validator(mode="after")
    def _validate_production_safety(self) -> Settings:
        if self.smtp_listener_enabled:
            try:
                networks = self.smtp_listener_networks()
            except ValueError as exc:
                raise ValueError(
                    f"SMTP_LISTENER_ALLOWED_CLIENTS is not a list of IPs/CIDRs: {exc}"
                ) from exc
            if not networks:
                raise ValueError(
                    "SMTP_LISTENER_ENABLED=true needs SMTP_LISTENER_ALLOWED_CLIENTS "
                    "(the forwarding mail server's IP)"
                )
        if self.app_env.strip().lower() == "production":
            if self.diagnostic_mode == "simulated":
                raise ValueError(
                    "DIAGNOSTIC_MODE='simulated' is forbidden when APP_ENV='production'"
                )
            if self.loop_guard_fail_open_for_tests:
                raise ValueError(
                    "LOOP_GUARD_FAIL_OPEN_FOR_TESTS=True is forbidden when APP_ENV='production'"
                )
            if self.smtp_listener_enabled and any(
                net.prefixlen == 0 for net in self.smtp_listener_networks()
            ):
                raise ValueError(
                    "SMTP_LISTENER_ALLOWED_CLIENTS must not allow every address when "
                    "APP_ENV='production'; list the forwarding mail server's IP"
                )
        return self

    def smtp_listener_networks(self) -> list[IPv4Network | IPv6Network]:
        """Parse `SMTP_LISTENER_ALLOWED_CLIENTS`; a bare IP means that single host."""
        return [
            ip_network(item.strip(), strict=False)
            for item in self.smtp_listener_allowed_clients.split(",")
            if item.strip()
        ]

    def smtp_listener_recipients(self) -> set[str]:
        return {
            item.strip().lower()
            for item in self.smtp_listener_allowed_recipients.split(",")
            if item.strip()
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
