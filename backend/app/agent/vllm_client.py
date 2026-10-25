"""OpenAI-compatible async client targeting Gemma 4 26B A4B NVFP4 on vLLM (10.100.109.9:8002)."""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Optional, TypeVar, Union

import httpx
from pydantic import BaseModel

from app.common.config import get_settings
from app.common.exceptions import LLMInferenceError

logger = logging.getLogger("it_net.vllm")

T = TypeVar("T", bound=BaseModel)

_http_clients: dict[str, httpx.AsyncClient] = {}
VllmOverrideCallable = Callable[
    [list[dict[str, Any]], type[BaseModel], Optional[list[bytes]]],
    Union[BaseModel, dict[str, Any], str, Awaitable[Union[BaseModel, dict[str, Any], str]]],
]
_vllm_override_handler: Optional[VllmOverrideCallable] = None


def set_vllm_override(
    handler: Optional[VllmOverrideCallable],
) -> None:
    """Install or clear an override handler (e.g. `FakeVllm` in unit/integration tests)."""
    global _vllm_override_handler
    _vllm_override_handler = handler


def get_vllm_override() -> Optional[VllmOverrideCallable]:
    return _vllm_override_handler


def normalize_vllm_base_url(endpoint: str) -> str:
    """Accept `http://host:8002`, `http://host:8002/` or `http://host:8002/v1` (the Page 12 form)."""
    base = endpoint.strip().rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    return base


@dataclass(frozen=True)
class VllmCallOptions:
    """Per-call vLLM settings taken from Page 12 (`system_settings`)."""

    base_url: str
    temperature: float
    max_tokens: int


def get_vllm_http_client(base_url: Optional[str] = None) -> httpx.AsyncClient:
    """Return the shared, connection-pooled client for `base_url` (one pool per endpoint).

    Changing the endpoint on Page 12 opens a new pool; old pools are closed at shutdown.
    """
    settings = get_settings()
    key = normalize_vllm_base_url(base_url or settings.vllm_base_url)
    client = _http_clients.get(key)
    if client is None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if settings.vllm_api_key:
            headers["Authorization"] = f"Bearer {settings.vllm_api_key}"
        client = httpx.AsyncClient(
            base_url=key,
            headers=headers,
            timeout=httpx.Timeout(settings.llm_request_timeout_sec, connect=5.0),
            limits=httpx.Limits(
                max_connections=settings.vllm_pool_max_connections,
                max_keepalive_connections=settings.vllm_pool_max_keepalive,
                keepalive_expiry=settings.vllm_pool_keepalive_expiry_sec,
            ),
        )
        _http_clients[key] = client
    return client


async def aclose_vllm_client() -> None:
    """Cleanly close every vLLM HTTP connection pool on FastAPI shutdown."""
    clients = list(_http_clients.values())
    _http_clients.clear()
    for client in clients:
        await client.aclose()


def _strip_json_fences(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


async def guided_json(
    messages: list[dict[str, Any]],
    schema: type[T],
    *,
    images: Optional[list[bytes]] = None,
    options: Optional[VllmCallOptions] = None,
) -> T:
    """Call `vLLM` `/v1/chat/completions` with `guided_json=schema.model_json_schema()`, validate with Pydantic, and retry with backoff."""
    settings = get_settings()
    max_attempts = max(1, int(settings.llm_max_retries))

    formatted_messages: list[dict[str, Any]] = []
    for idx, msg in enumerate(messages):
        if images and idx == len(messages) - 1 and msg.get("role") == "user":
            content_parts: list[dict[str, Any]] = [
                {"type": "text", "text": str(msg.get("content", ""))}
            ]
            for img_bytes in images[:5]:
                b64 = base64.b64encode(img_bytes).decode("ascii")
                content_parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                )
            formatted_messages.append({"role": "user", "content": content_parts})
        else:
            formatted_messages.append(dict(msg))

    json_schema = schema.model_json_schema()
    payload: dict[str, Any] = {
        "model": settings.default_worker_model,
        "messages": formatted_messages,
        "temperature": options.temperature if options is not None else settings.vllm_temperature,
        "max_tokens": options.max_tokens if options is not None else settings.vllm_max_tokens,
        "guided_json": json_schema,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": json_schema,
            },
        },
    }

    last_exc: Optional[Exception] = None
    for attempt in range(max_attempts):
        try:
            if _vllm_override_handler is not None:
                raw_res = _vllm_override_handler(messages, schema, images)
                res_obj = await raw_res if inspect.isawaitable(raw_res) else raw_res
                if isinstance(res_obj, schema):
                    return res_obj
                if isinstance(res_obj, dict):
                    return schema.model_validate(res_obj)
                if isinstance(res_obj, str):
                    return schema.model_validate_json(_strip_json_fences(res_obj))
                return schema.model_validate_json(json.dumps(res_obj.model_dump()))

            client = get_vllm_http_client(options.base_url if options else None)
            resp = await client.post(
                "/v1/chat/completions",
                json=payload,
                timeout=settings.llm_request_timeout_sec,
            )
            if resp.status_code != 200:
                raise LLMInferenceError(f"HTTP {resp.status_code} from vLLM: {resp.text[:250]}")
            body = resp.json()
            choices = body.get("choices") or []
            if not choices:
                raise LLMInferenceError("Empty choices array returned by vLLM")
            raw_content = str((choices[0].get("message") or {}).get("content") or "")
            cleaned = _strip_json_fences(raw_content)
            return schema.model_validate_json(cleaned)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "vLLM guided_json attempt %d/%d failed for schema=%s: %s",
                attempt + 1,
                max_attempts,
                schema.__name__,
                exc,
            )
            if attempt + 1 < max_attempts:
                await asyncio.sleep(0.02 * (2**attempt))

    if isinstance(last_exc, LLMInferenceError):
        raise last_exc
    raise LLMInferenceError(
        f"Failed after {max_attempts} attempts for {schema.__name__}: {last_exc}"
    ) from last_exc


async def probe_vllm_endpoint(endpoint: str, timeout_sec: float = 5.0) -> dict[str, Any]:
    """Call `GET /v1/models` on `endpoint` and report reachability, latency and whether the
    configured model (`DEFAULT_WORKER_MODEL`) is actually served."""
    settings = get_settings()
    base_url = normalize_vllm_base_url(endpoint)
    result: dict[str, Any] = {
        "ok": False,
        "endpoint": base_url,
        "configured_model": settings.default_worker_model,
        "model_available": False,
        "available_models": [],
        "error": None,
    }
    started = time.perf_counter()
    try:
        resp = await get_vllm_http_client(base_url).get("/v1/models", timeout=timeout_sec)
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code} from {base_url}/v1/models"
        else:
            data = resp.json()
            models = [
                str(m.get("id"))
                for m in data.get("data", [])
                if isinstance(m, dict) and m.get("id")
            ]
            result["available_models"] = models
            result["model_available"] = settings.default_worker_model in models
            result["ok"] = result["model_available"]
            if not result["model_available"]:
                result["error"] = (
                    f"Server is up but does not serve '{settings.default_worker_model}' "
                    f"(serves: {', '.join(models) or 'none'})"
                )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    result["latency_ms"] = int((time.perf_counter() - started) * 1000)
    return result
