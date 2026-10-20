"""Structured logging setup with automatic credential and secret redaction."""

from __future__ import annotations

import logging
import re
import sys

PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-\._~\+\/]+=*", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    (re.compile(r"(password\s*[=:]\s*)[^\s&,;\"']+", re.IGNORECASE), r"\1[REDACTED_PASSWORD]"),
    (re.compile(r"(secret_key\s*[=:]\s*)[^\s&,;\"']+", re.IGNORECASE), r"\1[REDACTED_SECRET]"),
]


class SecretRedactingFormatter(logging.Formatter):
    """Logging formatter that scrubs tokens and credentials from log lines."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern, replacement in PATTERNS:
            redacted = pattern.sub(replacement, redacted)
        return redacted


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure root logger with the redaction formatter."""
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = SecretRedactingFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)
    root_logger.addHandler(handler)
