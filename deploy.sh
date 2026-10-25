#!/usr/bin/env bash
# ==============================================================================
# IT Network Support AI Agent — Multi-Environment Remote Deployment Script
# ==============================================================================
# Deploys code to 10.100.109.9 (or any remote Docker host) into strictly isolated
# DEV or PROD container stacks on the same server.
#
# Dual Environment Layout on 10.100.109.9:
#   DEV  (--env dev)  [Default]:
#     • Remote Dir    : ~/it-network-support-agent-dev
#     • Project Name  : it-net-support-dev
#     • Containers    : it-net-agent-dev, it-net-postgres-dev, it-net-redis-dev
#     • Host Ports    : Web/API :8085 | Postgres :5435 | Redis :6385
#
#   PROD (--env prod):
#     • Remote Dir    : ~/it-network-support-agent-prod
#     • Project Name  : it-net-support-prod
#     • Containers    : it-net-agent-prod, it-net-postgres-prod, it-net-redis-prod
#     • Host Ports    : Web/API :8084 | Postgres :5434 | Redis :6384
#
# Usage:
#   ./deploy.sh --env dev                - Deploy to DEV environment on 10.100.109.9
#   ./deploy.sh --env prod               - Deploy to PROD environment on 10.100.109.9
#   ./deploy.sh --env dev --status       - Check DEV containers status
#   ./deploy.sh --env prod --logs        - Tail PROD containers logs
#   ./deploy.sh --env dev --sync-only    - Sync code only without rebuilding
#   ./deploy.sh --env dev --build-only   - Trigger remote build without syncing
#   ./deploy.sh --env dev --restart      - Restart DEV containers
#   ./deploy.sh --env dev --down         - Stop DEV containers
# ==============================================================================

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ANSI Colors
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_RED="\033[1;31m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_BLUE="\033[1;34m"
CLR_CYAN="\033[1;36m"
CLR_DIM="\033[2m"

log_info() {
    echo -e "${CLR_BLUE}ℹ [INFO]${CLR_RESET} $1"
}

log_success() {
    echo -e "${CLR_GREEN}✔ [SUCCESS]${CLR_RESET} $1"
}

log_warn() {
    echo -e "${CLR_YELLOW}⚠ [WARN]${CLR_RESET} $1"
}

log_error() {
    echo -e "${CLR_RED}✖ [ERROR]${CLR_RESET} $1"
}

banner() {
    echo -e "${CLR_CYAN}${CLR_BOLD}"
    echo "======================================================================"
    echo "   IT NETWORK SUPPORT AI AGENT — MULTI-ENV REMOTE DEPLOYMENT TOOL     "
    echo "======================================================================"
    echo -e "${CLR_RESET}"
}

# ------------------------------------------------------------------------------
# 1. Argument Parsing & Environment Selection (dev vs prod)
# ------------------------------------------------------------------------------
TARGET_ENV="dev"
MODE="full"
DRY_RUN=""
NO_BUILD="0"
CUSTOM_PORT=""
CUSTOM_REMOTE_DIR=""
CUSTOM_HOST=""
CUSTOM_USER=""

show_help() {
    banner
    echo "Usage: ./deploy.sh [--env dev|prod] [TARGET] [OPTIONS]"
    echo ""
    echo "Environments (both hosted on 10.100.109.9 with separate containers & volumes):"
    echo "  --env dev        Deploy to DEV  (containers: it-net-*-dev,  App :8085, PG :5435, Redis :6385)"
    echo "  --env prod       Deploy to PROD (containers: it-net-*-prod, App :8084, PG :5434, Redis :6384)"
    echo ""
    echo "Options:"
    echo "  --port <port>    Override exposed host port for web/API"
    echo "  --sync-only      Sync source files to server only (no docker build/up)"
    echo "  --build-only     Run remote docker compose build and up (skip file sync)"
    echo "  --logs           Follow live logs from remote environment containers"
    echo "  --status         Show remote container status (docker compose ps)"
    echo "  --restart        Restart remote environment containers without rebuilding"
    echo "  --down           Stop remote environment containers"
    echo "  --no-build       Skip docker compose build (run synced code via live volume mounts)"
    echo "  --dry-run        Show which files rsync will transfer without copying"
    echo "  --help, -h       Show this help banner"
    echo ""
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env|-e)
            TARGET_ENV="$(echo "$2" | tr '[:upper:]' '[:lower:]')"
            if [[ "$TARGET_ENV" != "dev" && "$TARGET_ENV" != "prod" ]]; then
                log_error "Invalid --env '$2'. Must be 'dev' or 'prod'."
                exit 1
            fi
            shift 2
            ;;
        --port)
            CUSTOM_PORT="$2"
            shift 2
            ;;
        --sync-only)
            MODE="sync"
            shift
            ;;
        --build-only)
            MODE="build"
            shift
            ;;
        --logs)
            MODE="logs"
            shift
            ;;
        --status)
            MODE="status"
            shift
            ;;
        --restart)
            MODE="restart"
            shift
            ;;
        --down)
            MODE="down"
            shift
            ;;
        --no-build)
            NO_BUILD="1"
            shift
            ;;
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            TARGET="$1"
            if [[ "$TARGET" =~ ^([^@]+)@([^:]+):(.+)$ ]]; then
                CUSTOM_USER="${BASH_REMATCH[1]}"
                CUSTOM_HOST="${BASH_REMATCH[2]}"
                CUSTOM_REMOTE_DIR="${BASH_REMATCH[3]}"
            elif [[ "$TARGET" =~ ^([^@]+)@([^:]+)$ ]]; then
                CUSTOM_USER="${BASH_REMATCH[1]}"
                CUSTOM_HOST="${BASH_REMATCH[2]}"
            elif [[ "$TARGET" =~ ^([^:]+):(.+)$ ]]; then
                CUSTOM_HOST="${BASH_REMATCH[1]}"
                CUSTOM_REMOTE_DIR="${BASH_REMATCH[2]}"
            elif [[ "$TARGET" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || [[ "$TARGET" =~ ^[a-zA-Z0-9.-]+$ ]]; then
                CUSTOM_HOST="$TARGET"
            else
                log_error "Unrecognized target or option: '$1'"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# ------------------------------------------------------------------------------
# 2. Resolve Environment-Specific Defaults (DEV vs PROD on 10.100.109.9)
# ------------------------------------------------------------------------------
LOCAL_ENV_FILE="$SCRIPT_DIR/.env.${TARGET_ENV}"
if [ ! -f "$LOCAL_ENV_FILE" ] && [ -f "$SCRIPT_DIR/.env" ]; then
    LOCAL_ENV_FILE="$SCRIPT_DIR/.env"
fi

if [ -f "$LOCAL_ENV_FILE" ]; then
    DEPLOY_HOST_CONFIG=$(grep -E '^(DEPLOY_HOST|SERVER_HOST)=' "$LOCAL_ENV_FILE" | head -n1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
    DEPLOY_USER_CONFIG=$(grep -E '^(DEPLOY_USER|SERVER_USER)=' "$LOCAL_ENV_FILE" | head -n1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
    DEPLOY_PORT_CONFIG=$(grep -E '^(DEPLOY_PORT|SERVER_SSH_PORT)=' "$LOCAL_ENV_FILE" | head -n1 | cut -d'=' -f2- | tr -d '"' | tr -d "'" || true)
fi

SERVER_USER="${CUSTOM_USER:-${DEPLOY_USER_CONFIG:-kazyon}}"
SERVER_HOST="${CUSTOM_HOST:-${DEPLOY_HOST_CONFIG:-10.100.109.9}}"
SSH_PORT="${DEPLOY_PORT_CONFIG:-22}"

if [ "$TARGET_ENV" = "prod" ]; then
    ENV_SLUG="prod"
    TARGET_ENV_UPPER="PROD"
    APP_ENV_VAL="production"
    COMPOSE_PROJECT="it-net-support-prod"
    IMAGE_NAME="it-net-support-agent-prod"
    DEFAULT_REMOTE_DIR="~/it-network-support-agent-prod"
    DEFAULT_APP_PORT="8084"
    DEFAULT_PG_PORT="5434"
    DEFAULT_REDIS_PORT="6384"
    DEFAULT_SMTP_LISTENER_PORT="2524"
    DEFAULT_PG_DB="it_net_support_prod"
    DEFAULT_PG_USER="it_net_prod"
    ENV_TEMPLATE_FILE=".env.prod.example"
else
    ENV_SLUG="dev"
    TARGET_ENV_UPPER="DEV"
    APP_ENV_VAL="development"
    COMPOSE_PROJECT="it-net-support-dev"
    IMAGE_NAME="it-net-support-agent-dev"
    DEFAULT_REMOTE_DIR="~/it-network-support-agent-dev"
    DEFAULT_APP_PORT="8085"
    DEFAULT_PG_PORT="5435"
    DEFAULT_REDIS_PORT="6385"
    DEFAULT_SMTP_LISTENER_PORT="2525"
    DEFAULT_PG_DB="it_net_support_dev"
    DEFAULT_PG_USER="it_net_dev"
    ENV_TEMPLATE_FILE=".env.dev.example"
fi

REMOTE_DIR="${CUSTOM_REMOTE_DIR:-$DEFAULT_REMOTE_DIR}"
APP_PORT="${CUSTOM_PORT:-$DEFAULT_APP_PORT}"
APP_SCHEME="http"
WS_SCHEME="ws"

# ------------------------------------------------------------------------------
# 3. SSH Command Helpers & ControlMaster Multiplexing
# ------------------------------------------------------------------------------
mkdir -p "$HOME/.ssh/sockets" 2>/dev/null || true
if [ -S "$HOME/.ssh/sockets/kazyon-${SERVER_USER}@${SERVER_HOST}-${SSH_PORT}" ]; then
    SSH_SOCKET="$HOME/.ssh/sockets/kazyon-%r@%h-%p"
else
    SSH_SOCKET="$HOME/.ssh/sockets/it-net-%r@%h-%p"
fi
SSH_OPTS=(-p "$SSH_PORT" -o ConnectTimeout=10 -o ControlMaster=auto -o ControlPath="$SSH_SOCKET" -o ControlPersist=300)

run_remote() {
    local cmd="$1"
    ssh "${SSH_OPTS[@]}" "${SERVER_USER}@${SERVER_HOST}" "$cmd"
}

check_ssh_connection() {
    log_info "Target Environment : ${CLR_BOLD}${TARGET_ENV_UPPER}${CLR_RESET} (Project: ${CLR_CYAN}${COMPOSE_PROJECT}${CLR_RESET})"
    log_info "Connecting to ${CLR_BOLD}${SERVER_USER}@${SERVER_HOST}:${SSH_PORT}${CLR_RESET}..."

    if [ -S "$SSH_SOCKET" ]; then
        if ! ssh -O check -o ControlPath="$SSH_SOCKET" "${SERVER_USER}@${SERVER_HOST}" &>/dev/null; then
            rm -f "$SSH_SOCKET" 2>/dev/null || true
        fi
    fi

    if ! ssh "${SSH_OPTS[@]}" "${SERVER_USER}@${SERVER_HOST}" "true"; then
        log_error "Failed to connect to ${SERVER_USER}@${SERVER_HOST} via SSH (Port ${SSH_PORT})."
        exit 1
    fi

    local REMOTE_PWD
    REMOTE_PWD=$(ssh "${SSH_OPTS[@]}" "${SERVER_USER}@${SERVER_HOST}" 'pwd')

    if [[ "$REMOTE_DIR" == "~"* ]]; then
        REMOTE_DIR="${REMOTE_PWD}${REMOTE_DIR:1}"
    elif [[ "$REMOTE_DIR" != "/"* ]]; then
        REMOTE_DIR="${REMOTE_PWD}/${REMOTE_DIR}"
    fi

    log_success "SSH connection established (Remote Dir: ${REMOTE_DIR})."
}

# ------------------------------------------------------------------------------
# 4. Sync, Build & Run Actions
# ------------------------------------------------------------------------------
sync_code() {
    if [ -d "$SCRIPT_DIR/frontend" ] && [ -f "$SCRIPT_DIR/frontend/package.json" ]; then
        if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
            log_info "Installing frontend dependencies locally..."
            ( cd "$SCRIPT_DIR/frontend" && npm install )
        fi
        log_info "Building fresh frontend assets locally before sync..."
        rm -rf "$SCRIPT_DIR/frontend/dist"
        ( cd "$SCRIPT_DIR/frontend" && npm run build )
    fi

    log_info "Syncing source code to [${TARGET_ENV_UPPER}] directory: ${CLR_CYAN}${REMOTE_DIR}${CLR_RESET}..."

    run_remote "mkdir -p '${REMOTE_DIR}/data/imports' '${REMOTE_DIR}/data/logs' '${REMOTE_DIR}/certs' '${REMOTE_DIR}/backups'"

    local START_TIME
    START_TIME=$(date +%s)

    rsync -avz --delete \
        -e "ssh -p ${SSH_PORT} -o ControlPath='${SSH_SOCKET}'" \
        $DRY_RUN \
        --exclude='.git/' \
        --exclude='.venv/' \
        --exclude='venv/' \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache/' \
        --exclude='.mypy_cache/' \
        --exclude='.ruff_cache/' \
        --exclude='frontend/node_modules/' \
        --exclude='frontend/npm_cache/' \
        --exclude='frontend/.vite/' \
        --exclude='data/' \
        --exclude='docs/' \
        --exclude='.DS_Store' \
        --exclude='.env' \
        --exclude='.env.dev' \
        --exclude='.env.prod' \
        --exclude='certs/' \
        --exclude='backups/' \
        --exclude='config-backups/' \
        "$SCRIPT_DIR/" "${SERVER_USER}@${SERVER_HOST}:${REMOTE_DIR}/"

    local END_TIME
    END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))

    if [ -n "$DRY_RUN" ]; then
        log_info "Dry-run complete. No files were transferred."
        exit 0
    fi

    log_success "Source code synced in ${DURATION}s."

    # Initialize and pin environment-specific variables in remote .env
    run_remote "
        if [ ! -f '${REMOTE_DIR}/.env' ]; then
            if [ -f '${REMOTE_DIR}/${ENV_TEMPLATE_FILE}' ]; then
                echo '[INFO] Creating initial .env from ${ENV_TEMPLATE_FILE} on server...'
                cp '${REMOTE_DIR}/${ENV_TEMPLATE_FILE}' '${REMOTE_DIR}/.env'
            elif [ -f '${REMOTE_DIR}/.env.example' ]; then
                cp '${REMOTE_DIR}/.env.example' '${REMOTE_DIR}/.env'
            else
                touch '${REMOTE_DIR}/.env'
            fi

            # Generate strong unique passwords/keys automatically on first creation if placeholders exist
            GEN_SECRET=\$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p -c 32)
            GEN_CRYPTO=\$(openssl rand -base64 24 2>/dev/null | head -c 32)
            GEN_PG_PASS=\$(openssl rand -hex 16 2>/dev/null || echo 'it_net_${ENV_SLUG}_pg_2026')
            GEN_REDIS_PASS=\$(openssl rand -hex 16 2>/dev/null || echo 'it_net_${ENV_SLUG}_redis_2026')
            GEN_ADMIN_PASS=\$(openssl rand -base64 12 2>/dev/null || echo 'Admin_${ENV_SLUG}_2026!')

            sed -i \"s|REPLACE_WITH_OPENSSL_RAND_HEX_32_IN_PROD|\${GEN_SECRET}|g\" '${REMOTE_DIR}/.env'
            sed -i \"s|REPLACE_WITH_32_BYTE_KEY_IN_PROD|\${GEN_CRYPTO}|g\" '${REMOTE_DIR}/.env'
            sed -i \"s|REPLACE_WITH_STRONG_PG_PASSWORD_IN_PROD|\${GEN_PG_PASS}|g\" '${REMOTE_DIR}/.env'
            sed -i \"s|REPLACE_WITH_STRONG_REDIS_PASSWORD_IN_PROD|\${GEN_REDIS_PASS}|g\" '${REMOTE_DIR}/.env'
            sed -i \"s|REPLACE_WITH_STRONG_ADMIN_PASSWORD_IN_PROD|\${GEN_ADMIN_PASS}|g\" '${REMOTE_DIR}/.env'
        fi

        # Pin isolation variables so dev and prod never collide on 10.100.109.9
        grep -q '^ENV_SLUG=' '${REMOTE_DIR}/.env' && sed -i 's/^ENV_SLUG=.*/ENV_SLUG=${ENV_SLUG}/' '${REMOTE_DIR}/.env' || echo 'ENV_SLUG=${ENV_SLUG}' >> '${REMOTE_DIR}/.env'
        grep -q '^APP_ENV=' '${REMOTE_DIR}/.env' && sed -i 's/^APP_ENV=.*/APP_ENV=${APP_ENV_VAL}/' '${REMOTE_DIR}/.env' || echo 'APP_ENV=${APP_ENV_VAL}' >> '${REMOTE_DIR}/.env'
        grep -q '^COMPOSE_PROJECT_NAME=' '${REMOTE_DIR}/.env' && sed -i 's/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT}/' '${REMOTE_DIR}/.env' || echo 'COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT}' >> '${REMOTE_DIR}/.env'
        grep -q '^IMAGE_NAME=' '${REMOTE_DIR}/.env' && sed -i 's/^IMAGE_NAME=.*/IMAGE_NAME=${IMAGE_NAME}/' '${REMOTE_DIR}/.env' || echo 'IMAGE_NAME=${IMAGE_NAME}' >> '${REMOTE_DIR}/.env'
        grep -q '^APP_PORT=' '${REMOTE_DIR}/.env' && sed -i 's/^APP_PORT=.*/APP_PORT=${APP_PORT}/' '${REMOTE_DIR}/.env' || echo 'APP_PORT=${APP_PORT}' >> '${REMOTE_DIR}/.env'
        grep -q '^POSTGRES_PORT=' '${REMOTE_DIR}/.env' && sed -i 's/^POSTGRES_PORT=.*/POSTGRES_PORT=${DEFAULT_PG_PORT}/' '${REMOTE_DIR}/.env' || echo 'POSTGRES_PORT=${DEFAULT_PG_PORT}' >> '${REMOTE_DIR}/.env'
        grep -q '^REDIS_PORT=' '${REMOTE_DIR}/.env' && sed -i 's/^REDIS_PORT=.*/REDIS_PORT=${DEFAULT_REDIS_PORT}/' '${REMOTE_DIR}/.env' || echo 'REDIS_PORT=${DEFAULT_REDIS_PORT}' >> '${REMOTE_DIR}/.env'
        grep -q '^SMTP_LISTENER_PUBLISH_PORT=' '${REMOTE_DIR}/.env' && sed -i 's/^SMTP_LISTENER_PUBLISH_PORT=.*/SMTP_LISTENER_PUBLISH_PORT=${DEFAULT_SMTP_LISTENER_PORT}/' '${REMOTE_DIR}/.env' || echo 'SMTP_LISTENER_PUBLISH_PORT=${DEFAULT_SMTP_LISTENER_PORT}' >> '${REMOTE_DIR}/.env'

        # Ensure vLLM points to Gemma 4 26B A4B on 10.100.109.9:8002
        grep -q '^VLLM_BASE_URL=' '${REMOTE_DIR}/.env' && sed -i 's|^VLLM_BASE_URL=.*|VLLM_BASE_URL=http://10.100.109.9:8002|' '${REMOTE_DIR}/.env' || echo 'VLLM_BASE_URL=http://10.100.109.9:8002' >> '${REMOTE_DIR}/.env'
        grep -q '^DEFAULT_WORKER_MODEL=' '${REMOTE_DIR}/.env' && sed -i 's|^DEFAULT_WORKER_MODEL=.*|DEFAULT_WORKER_MODEL=google/gemma-4-26B-A4B-it|' '${REMOTE_DIR}/.env' || echo 'DEFAULT_WORKER_MODEL=google/gemma-4-26B-A4B-it' >> '${REMOTE_DIR}/.env'
        grep -q '^DEFAULT_ROUTER_MODEL=' '${REMOTE_DIR}/.env' && sed -i 's|^DEFAULT_ROUTER_MODEL=.*|DEFAULT_ROUTER_MODEL=google/gemma-4-26B-A4B-it|' '${REMOTE_DIR}/.env' || echo 'DEFAULT_ROUTER_MODEL=google/gemma-4-26B-A4B-it' >> '${REMOTE_DIR}/.env'
    "
}

remote_build_and_run() {
    log_info "Deploying [${TARGET_ENV_UPPER}] stack (${COMPOSE_PROJECT}) on ${SERVER_HOST}..."
    echo -e "${CLR_DIM}----------------------------------------------------------------------${CLR_RESET}"

    local START_TIME
    START_TIME=$(date +%s)

    run_remote "
        set -e
        cd '${REMOTE_DIR}'

        export DOCKER_BUILDKIT=1
        export COMPOSE_DOCKER_CLI_BUILD=1
        export ENV_SLUG='${ENV_SLUG}'
        export COMPOSE_PROJECT_NAME='${COMPOSE_PROJECT}'
        export APP_PORT='${APP_PORT}'

        BASE_SNAPSHOT='${IMAGE_NAME}-base:latest'
        if docker image inspect \"\${BASE_SNAPSHOT}\" >/dev/null 2>&1; then
            export BASE_IMAGE=\"\${BASE_SNAPSHOT}\"
        else
            export BASE_IMAGE='python:3.12-slim-bookworm'
        fi

        echo '🧹 Stopping existing [${TARGET_ENV_UPPER}] containers (volumes preserved)...'
        docker compose -p '${COMPOSE_PROJECT}' down --remove-orphans

        find backend -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
        find backend -name '*.py[cod]' -delete 2>/dev/null || true

        if [ '${NO_BUILD}' = '1' ]; then
            echo '⚡ Skipping docker compose build (--no-build active)...'
        else
            echo '⚙️ Building [${TARGET_ENV_UPPER}] image (${IMAGE_NAME}:latest)...'
            export CACHE_BUST=\$(date +%s)
            docker compose -p '${COMPOSE_PROJECT}' build
            if ! docker image inspect \"\${BASE_SNAPSHOT}\" >/dev/null 2>&1; then
                NEW_LAYERS=\$(docker inspect -f '{{len .RootFS.Layers}}' '${IMAGE_NAME}:latest' 2>/dev/null || echo 999)
                if [ \"\${NEW_LAYERS}\" -lt 50 ]; then
                    docker tag '${IMAGE_NAME}:latest' \"\${BASE_SNAPSHOT}\"
                fi
            fi
        fi

        echo '🗄️ Starting [${TARGET_ENV_UPPER}] Postgres (it-net-postgres-${ENV_SLUG}) and Redis (it-net-redis-${ENV_SLUG})...'
        docker compose -p '${COMPOSE_PROJECT}' up -d postgres redis
        for i in \$(seq 1 30); do
            docker compose -p '${COMPOSE_PROJECT}' exec -T postgres pg_isready -q && break
            sleep 1
        done

        echo '🧬 Applying database migrations (alembic upgrade head)...'
        docker compose -p '${COMPOSE_PROJECT}' run --rm --no-deps -T -w /app/backend it-net-agent alembic upgrade head

        echo '🚀 Starting [${TARGET_ENV_UPPER}] application container (it-net-agent-${ENV_SLUG}) on port ${APP_PORT}...'
        docker compose -p '${COMPOSE_PROJECT}' up -d --force-recreate --remove-orphans

        docker image prune -f >/dev/null || true
    "

    local END_TIME
    END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))

    echo -e "${CLR_DIM}----------------------------------------------------------------------${CLR_RESET}"
    log_success "[${TARGET_ENV_UPPER}] stack deployed & launched in ${DURATION}s."
}

check_health() {
    log_info "Checking [${TARGET_ENV_UPPER}] container health on ${SERVER_HOST}:${APP_PORT} ..."
    local MAX_RETRIES=15
    local COUNT=0
    local HEALTHY=0

    while [ $COUNT -lt $MAX_RETRIES ]; do
        sleep 2
        COUNT=$((COUNT + 1))
        local STATUS

        STATUS=$(run_remote "curl -s -o /dev/null -w '%{http_code}' http://localhost:${APP_PORT}/api/health 2>/dev/null || true")
        if [ "$STATUS" = "200" ]; then
            HEALTHY=1
            break
        fi

        STATUS=$(run_remote "curl -sk -o /dev/null -w '%{http_code}' https://localhost:${APP_PORT}/api/health 2>/dev/null || true")
        if [ "$STATUS" = "200" ]; then
            HEALTHY=1
            APP_SCHEME="https"
            WS_SCHEME="wss"
            break
        fi

        echo -n "."
    done
    echo ""

    if [ $HEALTHY -eq 1 ]; then
        log_success "IT Network Support Agent [${TARGET_ENV_UPPER}] is healthy and responding over ${APP_SCHEME} (HTTP 200)!"
    else
        log_warn "Health endpoint did not return HTTP 200 within 30s. Checking logs..."
        run_remote "cd '${REMOTE_DIR}' && docker compose -p '${COMPOSE_PROJECT}' logs --tail=30"
    fi
}

show_status() {
    log_info "Fetching [${TARGET_ENV_UPPER}] container status (${COMPOSE_PROJECT}) from ${SERVER_HOST}..."
    run_remote "cd '${REMOTE_DIR}' && docker compose -p '${COMPOSE_PROJECT}' ps"
}

tail_logs() {
    log_info "Streaming [${TARGET_ENV_UPPER}] logs (${COMPOSE_PROJECT}) from ${SERVER_HOST}..."
    run_remote "cd '${REMOTE_DIR}' && docker compose -p '${COMPOSE_PROJECT}' logs -f --tail=100"
}

restart_container() {
    log_info "Restarting [${TARGET_ENV_UPPER}] containers (${COMPOSE_PROJECT}) on ${SERVER_HOST}..."
    run_remote "cd '${REMOTE_DIR}' && docker compose -p '${COMPOSE_PROJECT}' restart"
    log_success "[${TARGET_ENV_UPPER}] containers restarted."
}

stop_container() {
    log_info "Stopping [${TARGET_ENV_UPPER}] containers (${COMPOSE_PROJECT}) on ${SERVER_HOST}..."
    run_remote "cd '${REMOTE_DIR}' && docker compose -p '${COMPOSE_PROJECT}' down"
    log_success "[${TARGET_ENV_UPPER}] containers stopped."
}

# ------------------------------------------------------------------------------
# 5. Main Execution Router
# ------------------------------------------------------------------------------
banner

case "$MODE" in
    sync)
        check_ssh_connection
        sync_code
        ;;
    build)
        check_ssh_connection
        remote_build_and_run
        check_health
        ;;
    logs)
        check_ssh_connection
        tail_logs
        ;;
    status)
        check_ssh_connection
        show_status
        ;;
    restart)
        check_ssh_connection
        restart_container
        ;;
    down)
        check_ssh_connection
        stop_container
        ;;
    full)
        check_ssh_connection
        sync_code
        remote_build_and_run
        check_health
        echo ""
        echo -e "${CLR_GREEN}${CLR_BOLD}======================================================================"
        echo "  🎉 Deployment Complete! [${TARGET_ENV_UPPER} ENVIRONMENT]"
        echo "  • Server:            ${SERVER_HOST}"
        echo "  • Compose Project:   ${COMPOSE_PROJECT}"
        echo "  • App Container:     it-net-agent-${ENV_SLUG}"
        echo "  • DB Container:      it-net-postgres-${ENV_SLUG} (Host Port: ${DEFAULT_PG_PORT})"
        echo "  • Redis Container:   it-net-redis-${ENV_SLUG} (Host Port: ${DEFAULT_REDIS_PORT})"
        echo "  • Web App (SPA):     ${APP_SCHEME}://${SERVER_HOST}:${APP_PORT}"
        echo "  • API & Swagger:     ${APP_SCHEME}://${SERVER_HOST}:${APP_PORT}/docs"
        echo "  • vLLM Engine:       http://10.100.109.9:8002 (Gemma 4 26B A4B NVFP4)"
        echo "  • Tail Logs:         ./deploy.sh --env ${TARGET_ENV} --logs"
        echo -e "======================================================================${CLR_RESET}"
        echo ""
        ;;
esac
