"""OpenAI-compatible async client targeting Gemma 4 26B A4B NVFP4 on vLLM (10.100.109.9:8002)."""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.common.config import get_settings

logger = logging.getLogger("it_net.vllm")

_http_client: Optional[httpx.AsyncClient] = None


def get_vllm_http_client() -> httpx.AsyncClient:
    """Return a shared, connection-pooled httpx.AsyncClient for vLLM requests."""
    global _http_client
    if _http_client is None:
        settings = get_settings()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.vllm_api_key:
            headers["Authorization"] = f"Bearer {settings.vllm_api_key}"
        _http_client = httpx.AsyncClient(
            base_url=settings.vllm_base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(
                max_connections=settings.vllm_pool_max_connections,
                max_keepalive_connections=settings.vllm_pool_max_keepalive,
                keepalive_expiry=settings.vllm_pool_keepalive_expiry_sec,
            ),
        )
    return _http_client


async def aclose_vllm_client() -> None:
    """Cleanly close the shared vLLM HTTP connection pool on FastAPI shutdown."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


async def check_vllm_health() -> dict[str, Any]:
    """Probe the vLLM server on 10.100.109.9:8002 to report model readiness."""
    settings = get_settings()
    client = get_vllm_http_client()
    try:
        resp = await client.get("/v1/models", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
            return {
                "reachable": True,
                "base_url": settings.vllm_base_url,
                "configured_model": settings.default_worker_model,
                "available_models": models,
            }
        return {
            "reachable": False,
            "base_url": settings.vllm_base_url,
            "configured_model": settings.default_worker_model,
            "status_code": resp.status_code,
        }
    except Exception as exc:
        logger.debug("vLLM health check unreachable (%s): %s", settings.vllm_base_url, exc)
        return {
            "reachable": False,
            "base_url": settings.vllm_base_url,
            "configured_model": settings.default_worker_model,
            "error": str(exc),
        }
