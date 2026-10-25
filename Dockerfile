# ==============================================================================
# IT Network Support AI Agent & Ticketing Harness — Container Runtime
# ==============================================================================
# BASE_IMAGE defaults to python:3.12-slim-bookworm for fresh builds, or can be
# set to a local cached base image for instant incremental rebuilds on 10.100.109.9.
ARG BASE_IMAGE=python:3.12-slim-bookworm
FROM ${BASE_IMAGE} AS runtime

WORKDIR /app

# Install network diagnostic system utilities (iputils-ping, traceroute, dnsutils, netcat)
# required by network troubleshooting scripts, guarded so cached base images skip apt.
RUN if ! command -v ping >/dev/null 2>&1 || ! command -v traceroute >/dev/null 2>&1; then \
        apt-get update && \
        apt-get install -y --no-install-recommends \
            iputils-ping \
            traceroute \
            dnsutils \
            netcat-openbsd \
            openssh-client \
            ca-certificates && \
        rm -rf /var/lib/apt/lists/* ; \
    fi

# Install Python backend dependencies using BuildKit pip cache mount
COPY backend/requirements.txt /app/backend/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    if python3 -c "import fastapi, uvicorn, sqlalchemy, aiosqlite, alembic, psycopg, redis, pydantic, pydantic_settings, httpx, websockets, cryptography, multipart, dotenv, pandas, openpyxl, bcrypt, jwt, pytest, yaml" >/dev/null 2>&1; then \
        echo "[deps] core requirements already installed in base image — skipping pip download." ; \
    else \
        echo "[deps] installing backend/requirements.txt (using /root/.cache/pip cache mount)..." && \
        pip install --prefer-binary --timeout 300 --retries 10 -r /app/backend/requirements.txt ; \
    fi

# Bust layer cache only from here down on every deploy so apt/pip layers stay cached,
# and wipe /app/backend + /app/frontend/dist first so zero stale files survive.
ARG CACHE_BUST=1
RUN rm -rf /app/backend /app/frontend/dist

# Copy backend application and operational scripts
COPY backend /app/backend

# Copy compiled frontend SPA assets
COPY frontend/dist /app/frontend/dist

ENV PYTHONPATH="/app/backend:${PYTHONPATH}" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

RUN mkdir -p /app/data/imports /app/data/logs /app/data/attachments && \
    chmod +x /app/backend/scripts/entrypoint.sh

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python3 /app/backend/scripts/healthcheck.py || exit 1

CMD ["/app/backend/scripts/entrypoint.sh"]
