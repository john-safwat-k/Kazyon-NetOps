#!/usr/bin/env bash
# ==============================================================================
# IT Network Support AI Agent — Local Development & Runner Script
# ==============================================================================
# Usage:
#   ./run.sh            - Run local dev environment (Backend :8000 + Frontend :5173)
#   ./run.sh dev        - Same as above
#   ./run.sh prod       - Build frontend & run unified FastAPI server on :8000
#   ./run.sh test       - Run backend automated test suite (Pytest)
#   ./run.sh lint       - Run ruff format/check and mypy type checking
#   ./run.sh build      - Build production frontend bundle
#   ./run.sh deploy-dev - Deploy to DEV containers on 10.100.109.9 (:8085)
#   ./run.sh deploy-prod- Deploy to PROD containers on 10.100.109.9 (:8084)
#   ./run.sh setup      - Install/update backend & frontend dependencies
# ==============================================================================

set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_DIR="$ROOT_DIR/.venv"

# ANSI Colors
CLR_RESET="\033[0m"
CLR_BOLD="\033[1m"
CLR_RED="\033[1;31m"
CLR_GREEN="\033[1;32m"
CLR_YELLOW="\033[1;33m"
CLR_BLUE="\033[1;34m"
CLR_CYAN="\033[1;36m"

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
    echo "       IT NETWORK SUPPORT AI AGENT — PLATFORM LAUNCHER                "
    echo "======================================================================"
    echo -e "${CLR_RESET}"
}

check_prerequisites() {
    log_info "Verifying system prerequisites..."

    if command -v python3.13 &>/dev/null; then
        PYTHON_CMD="python3.13"
    elif command -v python3.12 &>/dev/null; then
        PYTHON_CMD="python3.12"
    elif command -v python3.11 &>/dev/null; then
        PYTHON_CMD="python3.11"
    elif command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
    else
        log_error "Python 3 is required but was not found in PATH."
        exit 1
    fi

    if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
        log_error "Node.js and npm are required for the frontend."
        exit 1
    fi

    if [ ! -f "$ROOT_DIR/.env" ] && [ -f "$ROOT_DIR/.env.example" ]; then
        log_warn "No .env found. Generating template from .env.example..."
        cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    fi

    mkdir -p "$ROOT_DIR/data/imports" "$ROOT_DIR/data/logs"
}

setup_python_env() {
    if [ -d "$VENV_DIR" ] && ( [ ! -x "$VENV_DIR/bin/python" ] || ! "$VENV_DIR/bin/python" -c "import sys" &>/dev/null ); then
        log_warn "Existing virtual environment at $VENV_DIR is invalid. Recreating..."
        rm -rf "$VENV_DIR"
    fi

    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating Python virtual environment at $VENV_DIR using $PYTHON_CMD..."
        "$PYTHON_CMD" -m venv "$VENV_DIR"
    fi

    PYTHON_BIN="$VENV_DIR/bin/python"
    PIP_BIN="$VENV_DIR/bin/pip"

    if ! "$PYTHON_BIN" -c "import fastapi, sqlalchemy, pydantic, alembic, pytest" &>/dev/null; then
        log_info "Installing backend dependencies from backend/requirements.txt..."
        "$PIP_BIN" install -r "$BACKEND_DIR/requirements.txt"
        log_success "Backend dependencies installed successfully."
    fi
}

setup_frontend_env() {
    if [ ! -d "$FRONTEND_DIR/node_modules" ] || [ "$FRONTEND_DIR/package.json" -nt "$FRONTEND_DIR/node_modules" ]; then
        log_info "Installing / updating frontend npm dependencies..."
        ( cd "$FRONTEND_DIR" && npm install --cache "$FRONTEND_DIR/npm_cache" )
        log_success "Frontend packages installed successfully."
    fi
}

run_tests() {
    banner
    check_prerequisites
    setup_python_env
    log_info "Executing automated backend test suite..."
    ( cd "$BACKEND_DIR" && PYTHONPATH=. "$VENV_DIR/bin/pytest" tests/ -v )
    log_success "All tests passed cleanly."
}

run_lint() {
    banner
    check_prerequisites
    setup_python_env
    log_info "Running ruff check & mypy..."
    ( cd "$BACKEND_DIR" && "$VENV_DIR/bin/ruff" check app/ tests/ && "$VENV_DIR/bin/mypy" app/ )
    log_success "Lint and type checks passed cleanly."
}

build_frontend() {
    banner
    check_prerequisites
    setup_frontend_env
    log_info "Compiling frontend bundle with Vite..."
    ( cd "$FRONTEND_DIR" && npm run build )
    log_success "Production frontend bundle created in frontend/dist/"
}

run_dev() {
    banner
    check_prerequisites
    setup_python_env
    setup_frontend_env

    log_info "Starting IT Network Support AI Agent in ${CLR_BOLD}LOCAL DEVELOPMENT MODE${CLR_RESET}..."

    trap 'echo -e "\n${CLR_YELLOW}Shutting down all processes...${CLR_RESET}"; kill $(jobs -p) 2>/dev/null || true; exit 0' SIGINT SIGTERM EXIT

    log_info "Launching FastAPI backend on ${CLR_GREEN}http://localhost:8000${CLR_RESET}..."
    (
        cd "$BACKEND_DIR"
        PYTHONPATH=. "$VENV_DIR/bin/uvicorn" app.main:app --reload --host 0.0.0.0 --port 8000
    ) &

    log_info "Launching Vite Web UI on ${CLR_GREEN}http://localhost:5173${CLR_RESET}..."
    (
        cd "$FRONTEND_DIR"
        npm run dev
    ) &

    echo ""
    echo -e "${CLR_GREEN}${CLR_BOLD}======================================================================"
    echo "  🚀 IT Network Support AI Agent is running locally!"
    echo "  • Web UI (Kanban & Admin): http://localhost:5173"
    echo "  • Backend API & Docs:      http://localhost:8000/docs"
    echo "  • Health Endpoint:         http://localhost:8000/api/health"
    echo "======================================================================${CLR_RESET}"
    echo -e "${CLR_CYAN}Press Ctrl+C to terminate all services cleanly.${CLR_RESET}\n"

    wait
}

run_prod() {
    banner
    check_prerequisites
    setup_python_env
    setup_frontend_env

    log_info "Building latest frontend assets..."
    ( cd "$FRONTEND_DIR" && npm run build )

    log_info "Starting Unified Server on http://localhost:8000..."
    (
        cd "$BACKEND_DIR"
        PYTHONPATH=. "$VENV_DIR/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000
    )
}

show_help() {
    banner
    echo "Available commands:"
    echo "  ./run.sh [dev]         - Start local dev stack (Backend :8000 + Frontend :5173)"
    echo "  ./run.sh prod          - Build frontend and start unified FastAPI server on :8000"
    echo "  ./run.sh test          - Run automated unit and integration tests (Pytest)"
    echo "  ./run.sh lint          - Run ruff and mypy checks"
    echo "  ./run.sh build         - Compile frontend production bundle"
    echo "  ./run.sh deploy-dev    - Remote deploy to DEV stack on 10.100.109.9 (:8085)"
    echo "  ./run.sh deploy-prod   - Remote deploy to PROD stack on 10.100.109.9 (:8084)"
    echo "  ./run.sh setup         - Initialize / update Python and Node environments"
    echo "  ./run.sh help          - Show this help message"
    echo ""
}

MODE="${1:-dev}"

case "$MODE" in
    dev|start)
        run_dev
        ;;
    prod|production)
        run_prod
        ;;
    test|tests)
        run_tests
        ;;
    lint|check)
        run_lint
        ;;
    build)
        build_frontend
        ;;
    deploy-dev)
        shift || true
        "$ROOT_DIR/deploy.sh" --env dev "$@"
        ;;
    deploy-prod)
        shift || true
        "$ROOT_DIR/deploy.sh" --env prod "$@"
        ;;
    deploy)
        shift || true
        "$ROOT_DIR/deploy.sh" "$@"
        ;;
    setup|install)
        banner
        check_prerequisites
        setup_python_env
        setup_frontend_env
        log_success "Environment setup complete."
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: '$MODE'"
        show_help
        exit 1
        ;;
esac
