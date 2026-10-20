#!/usr/bin/env bash
# Container entrypoint: start uvicorn over HTTP or HTTPS if TLS certificates are configured.

set -euo pipefail

HOST="${UVICORN_HOST:-0.0.0.0}"
PORT="${UVICORN_PORT:-8000}"

CERTFILE="${HTTPS_CERTFILE:-}"
KEYFILE="${HTTPS_KEYFILE:-}"

if [ -n "$CERTFILE" ] && [ -z "$KEYFILE" ]; then
    echo "[entrypoint] FATAL: HTTPS_CERTFILE is set but HTTPS_KEYFILE is not. Set both, or neither." >&2
    exit 1
fi
if [ -z "$CERTFILE" ] && [ -n "$KEYFILE" ]; then
    echo "[entrypoint] FATAL: HTTPS_KEYFILE is set but HTTPS_CERTFILE is not. Set both, or neither." >&2
    exit 1
fi

if [ -n "$CERTFILE" ]; then
    for f in "$CERTFILE" "$KEYFILE"; do
        if [ ! -r "$f" ]; then
            echo "[entrypoint] FATAL: TLS requested but '$f' is missing or unreadable." >&2
            exit 1
        fi
    done

    echo "[entrypoint] Serving HTTPS on ${HOST}:${PORT} (cert: ${CERTFILE})."
    exec uvicorn app.main:app --host "$HOST" --port "$PORT" \
        --ssl-certfile "$CERTFILE" \
        --ssl-keyfile "$KEYFILE"
fi

echo "[entrypoint] Serving HTTP on ${HOST}:${PORT}."
exec uvicorn app.main:app --host "$HOST" --port "$PORT"
