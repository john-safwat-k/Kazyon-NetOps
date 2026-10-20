"""Domain exception hierarchy and RFC 7807 structured error handler."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class SupportAgentError(Exception):
    """Base exception for all IT Network Support AI Agent errors."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundError(SupportAgentError):
    """Raised when a requested domain entity cannot be found."""

    def __init__(self, entity_type: str, entity_id: Any) -> None:
        super().__init__(f"{entity_type} '{entity_id}' not found", status_code=404)
        self.entity_type = entity_type
        self.entity_id = entity_id


class DuplicateResourceError(SupportAgentError):
    """Raised when creating an entity that violates uniqueness."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=409)


class InvalidStateTransitionError(SupportAgentError):
    """Raised when a ticket state transition is not permitted."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class PermissionDeniedError(SupportAgentError):
    """Raised when a user lacks the required granular permission."""

    def __init__(self, permission: str) -> None:
        super().__init__(
            f"Missing required permission: '{permission}'",
            status_code=403,
            details={"required_permission": permission},
        )


class DiagnosticExecutionError(SupportAgentError):
    """Raised when a network troubleshooting script fails or times out."""

    def __init__(self, branch_code: str, message: str) -> None:
        super().__init__(
            f"Diagnostic script failed for branch '{branch_code}': {message}",
            status_code=502,
        )


class LLMInferenceError(SupportAgentError):
    """Raised when vLLM inference fails or returns invalid structured output."""

    def __init__(self, message: str) -> None:
        super().__init__(f"vLLM inference error: {message}", status_code=502)


class EmailDeliveryError(SupportAgentError):
    """Raised when inbound/outbound email transport encounters an error."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Email transport error: {message}", status_code=502)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global RFC 7807-style exception handlers on the FastAPI app."""

    @app.exception_handler(SupportAgentError)
    async def handle_domain_error(request: Request, exc: SupportAgentError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.__class__.__name__,
                "title": exc.message,
                "status": exc.status_code,
                "instance": str(request.url.path),
                "details": exc.details,
            },
        )
