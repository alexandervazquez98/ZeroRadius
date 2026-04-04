#!/usr/bin/env bash
#
# ZeroRadius — Test Pyramid Orchestrator
#
# Single entry point to run any combination of test layers.
# Default (no flags): fast local only (backend + frontend).
# Docker / heavy layers are strictly opt-in via explicit flags.
#
# Usage:
#   ./scripts/test-all.sh                      # fast local (default)
#   ./scripts/test-all.sh --full               # all layers
#   ./scripts/test-all.sh --with-docker --e2e  # docker stack + e2e
#   ./scripts/test-all.sh --radius             # fast + radius
#   ./scripts/test-all.sh --help               # show this help
#
# Layers (all opt-in except fast):
#   fast      Backend + frontend fast tests (DEFAULT)
#   docker    Docker Compose test stack (MariaDB + FreeRADIUS + backend)
#   radius    RADIUS protocol tests (pyrad)
#   e2e       Playwright E2E tests
#
# Flags:
#   --fast-only            Run ONLY fast local tests (explicit default)
#   --with-docker          Start docker-compose.test.yml for heavy layers
#   --radius               Run RADIUS tests (requires FreeRADIUS or --with-docker)
#   --e2e                  Run Playwright E2E tests
#   --full                 Shorthand for --with-docker --radius --e2e (plus fast)
#   --no-fast              Skip fast local tests
#   --continue-on-failure  Keep running remaining layers after a failure
#   --no-cleanup           Don't tear down Docker stack at the end
#   --help                 Show usage information
#
# Exit codes:
#   0   All requested layers passed
#   1   One or more layers failed (or pre-flight check failed)
#   2   Invalid arguments or usage error
#

set -euo pipefail

# ─── Resolve project root ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# ─── Defaults ────────────────────────────────────────────────────────────────
RUN_FAST=true
RUN_DOCKER=false
RUN_RADIUS=false
RUN_E2E=false
NO_FAST=false
CONTINUE_ON_FAILURE=false
NO_CLEANUP=false
DOCKER_COMPOSE_FILE="$PROJECT_ROOT/docker-compose.test.yml"
DOCKER_STACK_STARTED_BY_US=false

# ─── Colors (disabled if not a terminal) ─────────────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    CYAN=''
    BOLD=''
    NC=''
fi

# ─── Helpers ─────────────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}[test-all]${NC} $*"; }
ok()      { echo -e "${GREEN}[PASS]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()    { echo -e "${RED}[FAIL]${NC} $*"; }
section() { echo -e "\n${BOLD}═══════════════════════════════════════════════════════${NC}"; echo -e "${BOLD}  $*${NC}"; echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"; }

# Track results per layer
declare -A LAYER_STATUS=()
declare -A LAYER_EXIT=()
OVERALL_EXIT=0

record_result() {
    local layer="$1" exit_code="$2"
    LAYER_EXIT[$layer]=$exit_code
    if [ "$exit_code" -eq 0 ]; then
        LAYER_STATUS[$layer]="PASS"
        ok "$layer (exit 0)"
    else
        LAYER_STATUS[$layer]="FAIL"
        fail "$layer (exit $exit_code)"
        OVERALL_EXIT=1
    fi
}

# ─── Usage ───────────────────────────────────────────────────────────────────
usage() {
    cat <<'EOF'
ZeroRadius — Test Pyramid Orchestrator

USAGE:
  ./scripts/test-all.sh [OPTIONS]

LAYERS (all opt-in except fast):
  fast      Backend + frontend fast tests (DEFAULT)
  docker    Docker Compose test stack (MariaDB + FreeRADIUS + backend on :8001)
  radius    RADIUS protocol tests (pyrad, needs FreeRADIUS)
  e2e       Playwright E2E tests (needs frontend :5173 + backend :8000 or :8001)

FLAGS:
  --fast-only            Run ONLY fast local tests (explicit default)
  --with-docker          Start docker-compose.test.yml for heavy layers
  --radius               Run RADIUS tests (requires FreeRADIUS or --with-docker)
  --e2e                  Run Playwright E2E tests
  --full                 Shorthand for --with-docker --radius --e2e (plus fast)
  --no-fast              Skip fast local tests
  --continue-on-failure  Keep running remaining layers after a failure
  --no-cleanup           Don't tear down Docker stack at the end
  --help                 Show this help

EXAMPLES:
  ./scripts/test-all.sh                        # fast local only (default)
  ./scripts/test-all.sh --fast-only            # same as above, explicit
  ./scripts/test-all.sh --no-fast --with-docker  # docker stack only
  ./scripts/test-all.sh --radius               # fast + RADIUS
  ./scripts/test-all.sh --e2e                  # fast + E2E (local backend :8000)
  ./scripts/test-all.sh --full                 # fast + docker + radius + e2e
  ./scripts/test-all.sh --full --continue-on-failure  # run everything regardless
  ./scripts/test-all.sh --with-docker --e2e --no-cleanup  # docker + e2e, keep stack up

EXIT CODES:
  0   All requested layers passed
  1   One or more layers failed
  2   Invalid arguments or pre-flight failure
EOF
}

# ─── Parse arguments ─────────────────────────────────────────────────────────
while [ $# -gt 0 ]; do
    case "$1" in
        --help|-h)
            usage
            exit 0
            ;;
        --fast-only)
            RUN_FAST=true
            RUN_DOCKER=false
            RUN_RADIUS=false
            RUN_E2E=false
            shift
            ;;
        --with-docker)
            RUN_DOCKER=true
            shift
            ;;
        --radius)
            RUN_RADIUS=true
            shift
            ;;
        --e2e)
            RUN_E2E=true
            shift
            ;;
        --full)
            RUN_DOCKER=true
            RUN_RADIUS=true
            RUN_E2E=true
            RUN_FAST=true
            shift
            ;;
        --no-fast)
            NO_FAST=true
            RUN_FAST=false
            shift
            ;;
        --continue-on-failure)
            CONTINUE_ON_FAILURE=true
            shift
            ;;
        --no-cleanup)
            NO_CLEANUP=true
            shift
            ;;
        *)
            echo "ERROR: Unknown flag: $1"
            echo "Run './scripts/test-all.sh --help' for usage."
            exit 2
            ;;
    esac
done

# ─── Determine effective layers ──────────────────────────────────────────────
# If nothing was explicitly requested, default to fast only
if [ "$RUN_FAST" = false ] && [ "$RUN_DOCKER" = false ] && \
   [ "$RUN_RADIUS" = false ] && [ "$RUN_E2E" = false ]; then
    RUN_FAST=true
fi

# ─── Pre-flight checks ───────────────────────────────────────────────────────
section "Pre-flight checks"

PREFLIGHT_OK=true

# Check backend/.venv (only if fast tests will run)
if [ "$RUN_FAST" = true ]; then
    if [ ! -d "$PROJECT_ROOT/backend/.venv" ]; then
        fail "backend/.venv not found"
        echo "  Create it: cd backend && python -m venv .venv"
        echo "  Then:       source .venv/bin/activate && pip install -r requirements.txt -r requirements-test.txt"
        PREFLIGHT_OK=false
    else
        ok "backend/.venv exists"
    fi
fi

# Check frontend/node_modules (only if fast tests or E2E will run)
if [ "$RUN_FAST" = true ] || [ "$RUN_E2E" = true ]; then
    if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
        fail "frontend/node_modules not found"
        echo "  Run: cd frontend && npm install"
        PREFLIGHT_OK=false
    else
        ok "frontend/node_modules exists"
    fi
fi

# Check e2e/node_modules (only if E2E requested)
if [ "$RUN_E2E" = true ]; then
    if [ ! -d "$PROJECT_ROOT/e2e/node_modules" ]; then
        fail "e2e/node_modules not found"
        echo "  Run: cd e2e && npm install"
        PREFLIGHT_OK=false
    else
        ok "e2e/node_modules exists"
    fi
fi

# Check Docker availability (only if docker requested)
if [ "$RUN_DOCKER" = true ]; then
    if ! command -v docker &>/dev/null; then
        fail "docker not found in PATH"
        echo "  Install Docker Desktop or Docker Engine to use --with-docker"
        PREFLIGHT_OK=false
    elif ! docker info &>/dev/null 2>&1; then
        fail "docker daemon not running or not accessible"
        echo "  Start Docker Desktop or ensure the daemon is running"
        PREFLIGHT_OK=false
    else
        ok "docker available and running"
    fi

    if [ ! -f "$DOCKER_COMPOSE_FILE" ]; then
        fail "docker-compose.test.yml not found at $DOCKER_COMPOSE_FILE"
        PREFLIGHT_OK=false
    else
        ok "docker-compose.test.yml found"
    fi
fi

# Check radius-tests directory (only if radius requested)
if [ "$RUN_RADIUS" = true ]; then
    if [ ! -d "$PROJECT_ROOT/radius-tests" ]; then
        fail "radius-tests/ directory not found"
        PREFLIGHT_OK=false
    else
        ok "radius-tests/ directory exists"
    fi
fi

if [ "$PREFLIGHT_OK" = false ]; then
    echo ""
    fail "Pre-flight checks failed. Fix the issues above and try again."
    exit 2
fi

ok "All pre-flight checks passed"

# ─── Docker stack management ─────────────────────────────────────────────────
docker_start_stack() {
    section "Starting Docker test stack"
    info "Running: docker compose -f docker-compose.test.yml up -d"
    docker compose -f "$DOCKER_COMPOSE_FILE" up -d
    DOCKER_STACK_STARTED_BY_US=true

    # Wait for services to be healthy
    info "Waiting for services to be healthy..."
    local max_wait=90
    local waited=0
    local interval=5
    while [ $waited -lt $max_wait ]; do
        # Check if all services are healthy or running
        local status
        status=$(docker compose -f "$DOCKER_COMPOSE_FILE" ps --format json 2>/dev/null || echo "")
        if [ -n "$status" ]; then
            # Check for unhealthy services
            local unhealthy
            unhealthy=$(docker compose -f "$DOCKER_COMPOSE_FILE" ps --format "{{.Service}}: {{.Status}}" 2>/dev/null | grep -i "unhealthy" || true)
            if [ -z "$unhealthy" ]; then
                # No unhealthy services — check they're all at least "running"
                local all_running
                all_running=$(docker compose -f "$DOCKER_COMPOSE_FILE" ps --format "{{.Status}}" 2>/dev/null | grep -iv "running\|healthy\|up" || true)
                if [ -z "$all_running" ]; then
                    ok "All services are up"
                    return 0
                fi
            fi
        fi
        sleep $interval
        waited=$((waited + interval))
        info "  Waiting... (${waited}s / ${max_wait}s)"
    done

    warn "Timeout waiting for services to be healthy — proceeding anyway"
    docker compose -f "$DOCKER_COMPOSE_FILE" ps --format "{{.Service}}: {{.Status}}" 2>/dev/null || true
}

docker_stop_stack() {
    if [ "$DOCKER_STACK_STARTED_BY_US" = true ] && [ "$NO_CLEANUP" = false ]; then
        section "Tearing down Docker test stack"
        info "Running: docker compose -f docker-compose.test.yml down -v"
        docker compose -f "$DOCKER_COMPOSE_FILE" down -v
        DOCKER_STACK_STARTED_BY_US=false
        ok "Docker stack torn down"
    elif [ "$NO_CLEANUP" = true ] && [ "$DOCKER_STACK_STARTED_BY_US" = true ]; then
        warn "--no-cleanup: Docker stack left running"
    fi
}

# ─── Layer: Fast local ───────────────────────────────────────────────────────
run_fast() {
    section "Layer: Fast Local Tests"

    # Backend fast
    info "Running backend fast tests..."
    local backend_exit=0
    "$SCRIPT_DIR/test-backend-fast.sh" || backend_exit=$?
    record_result "backend-fast" $backend_exit

    if [ $backend_exit -ne 0 ] && [ "$CONTINUE_ON_FAILURE" = false ]; then
        fail "Backend fast tests failed — stopping (use --continue-on-failure to keep going)"
        return $backend_exit
    fi

    # Frontend fast
    info "Running frontend fast tests..."
    local frontend_exit=0
    "$SCRIPT_DIR/test-frontend-fast.sh" || frontend_exit=$?
    record_result "frontend-fast" $frontend_exit

    if [ $frontend_exit -ne 0 ] && [ "$CONTINUE_ON_FAILURE" = false ]; then
        fail "Frontend fast tests failed — stopping (use --continue-on-failure to keep going)"
        return $frontend_exit
    fi

    return 0
}

# ─── Layer: RADIUS ───────────────────────────────────────────────────────────
run_radius() {
    section "Layer: RADIUS Tests"

    # Determine RADIUS host/port based on whether Docker is up
    local radius_host="${RADIUS_HOST:-localhost}"
    local radius_port="${RADIUS_PORT:-1812}"

    if [ "$RUN_DOCKER" = true ] && [ "$DOCKER_STACK_STARTED_BY_US" = true ]; then
        radius_host="localhost"
        radius_port="1812"
        info "Using Docker FreeRADIUS at ${radius_host}:${radius_port}"
    else
        info "Using local FreeRADIUS at ${radius_host}:${radius_port}"
        # Quick connectivity check
        if ! command -v nc &>/dev/null && ! command -v ncat &>/dev/null; then
            warn "nc/ncat not available — skipping RADIUS connectivity pre-check"
        else
            local nc_cmd="nc"
            command -v ncat &>/dev/null && nc_cmd="ncat"
            if ! $nc_cmd -z -u -w2 "$radius_host" "$radius_port" 2>/dev/null; then
                warn "Cannot reach FreeRADIUS at ${radius_host}:${radius_port}"
                warn "RADIUS tests may fail. Start FreeRADIUS or use --with-docker."
            else
                ok "FreeRADIUS reachable at ${radius_host}:${radius_port}"
            fi
        fi
    fi

    info "Running RADIUS tests..."
    local radius_exit=0
    (
        cd "$PROJECT_ROOT/radius-tests"
        RADIUS_HOST="$radius_host" RADIUS_PORT="$radius_port" \
            python -m pytest . -v -m radius
    ) || radius_exit=$?
    record_result "radius" $radius_exit

    return $radius_exit
}

# ─── Layer: E2E ──────────────────────────────────────────────────────────────
run_e2e() {
    section "Layer: E2E Tests (Playwright)"

    # Detect backend port mismatch
    local expected_backend_port="8000"
    local vite_proxy_target=""

    # Try to extract proxy target from vite.config.js
    if [ -f "$PROJECT_ROOT/frontend/vite.config.js" ]; then
        vite_proxy_target=$(grep -oP "target:\s*'http://localhost:\K[0-9]+" \
            "$PROJECT_ROOT/frontend/vite.config.js" 2>/dev/null || echo "")
    fi

    if [ -n "$vite_proxy_target" ]; then
        if [ "$RUN_DOCKER" = true ] && [ "$DOCKER_STACK_STARTED_BY_US" = true ]; then
            # Docker mode: backend is on :8001, vite should proxy to :8001
            expected_backend_port="8001"
            if [ "$vite_proxy_target" != "8001" ]; then
                warn "⚠ PORT MISMATCH DETECTED"
                warn "  Docker backend runs on port 8001, but vite.config.js proxies to localhost:${vite_proxy_target}"
                warn "  E2E tests may fail. Either:"
                warn "    1. Change vite proxy target to http://localhost:8001 in vite.config.js"
                warn "  This script will NOT auto-patch your frontend config."
            else
                ok "Vite proxy target ($vite_proxy_target) matches Docker backend port"
            fi
        else
            # Local mode: backend should be on :8000
            expected_backend_port="8000"
            if [ "$vite_proxy_target" != "8000" ]; then
                warn "⚠ PORT MISMATCH DETECTED"
                warn "  Expected backend on port 8000, but vite.config.js proxies to localhost:${vite_proxy_target}"
                warn "  E2E tests may fail. Ensure your backend is running on the correct port."
            else
                ok "Vite proxy target ($vite_proxy_target) matches expected local backend port"
            fi
        fi
    else
        warn "Could not detect vite proxy target — skipping port mismatch check"
    fi

    # Check if backend is reachable on expected port
    if command -v curl &>/dev/null; then
        # Use a generic port check — Docker backend has DISABLE_DOCS=true so /docs returns 404.
        # We only need to verify the process is listening, not that a specific endpoint works.
        local backend_url="http://localhost:${expected_backend_port}"
        if ! curl -sf --max-time 3 "$backend_url" &>/dev/null; then
            warn "Backend not reachable at $backend_url"
            warn "E2E tests will likely fail. Start the backend first."
            if [ "$CONTINUE_ON_FAILURE" = false ]; then
                fail "Backend unreachable — stopping (use --continue-on-failure to skip this check)"
                LAYER_STATUS["e2e"]="SKIP"
                LAYER_EXIT["e2e"]=1
                OVERALL_EXIT=1
                return 1
            fi
        else
            ok "Backend reachable at localhost:${expected_backend_port}"
        fi
    fi

    info "Running Playwright E2E tests..."
    local e2e_exit=0
    (
        cd "$PROJECT_ROOT/e2e"
        # Use cmd /c on Windows, npx on Unix
        OS="$(uname -s)"
        if [[ "$OS" == MINGW* ]] || [[ "$OS" == MSYS* ]] || [[ "$OS" == CYGWIN* ]]; then
            cmd //c "node_modules\\.bin\\playwright.cmd test"
        else
            npx playwright test
        fi
    ) || e2e_exit=$?
    record_result "e2e" $e2e_exit

    return $e2e_exit
}

# ─── Final report ────────────────────────────────────────────────────────────
print_report() {
    section "Test Report"
    printf "${BOLD}%-20s %-10s %-10s${NC}\n" "LAYER" "STATUS" "EXIT"
    printf "%-20s %-10s %-10s\n" "--------------------" "----------" "----------"
    for layer in "${!LAYER_STATUS[@]}"; do
        local status="${LAYER_STATUS[$layer]}"
        local exit_code="${LAYER_EXIT[$layer]}"
        if [ "$status" = "PASS" ]; then
            printf "${GREEN}%-20s %-10s %-10s${NC}\n" "$layer" "$status" "$exit_code"
        elif [ "$status" = "SKIP" ]; then
            printf "${YELLOW}%-20s %-10s %-10s${NC}\n" "$layer" "$status" "$exit_code"
        else
            printf "${RED}%-20s %-10s %-10s${NC}\n" "$layer" "$status" "$exit_code"
        fi
    done
    echo ""
    if [ $OVERALL_EXIT -eq 0 ]; then
        echo -e "${GREEN}${BOLD}✓ All layers passed${NC}"
    else
        echo -e "${RED}${BOLD}✗ One or more layers failed${NC}"
    fi
}

# ─── Main execution ──────────────────────────────────────────────────────────
section "ZeroRadius Test Pyramid"
info "Layers to run:"
[ "$RUN_FAST" = true ]    && info "  ✓ Fast local (backend + frontend)"
[ "$RUN_DOCKER" = true ]  && info "  ✓ Docker test stack"
[ "$RUN_RADIUS" = true ]  && info "  ✓ RADIUS tests"
[ "$RUN_E2E" = true ]     && info "  ✓ E2E tests (Playwright)"
[ "$RUN_FAST" = false ]   && [ "$RUN_DOCKER" = false ] && \
[ "$RUN_RADIUS" = false ] && [ "$RUN_E2E" = false ] && info "  (none — nothing to run)"

info "Options:"
[ "$CONTINUE_ON_FAILURE" = true ] && info "  ✓ Continue on failure"
[ "$NO_CLEANUP" = true ]          && info "  ✓ No cleanup (Docker stack preserved)"

# Start Docker stack if requested and needed
if [ "$RUN_DOCKER" = true ]; then
    docker_start_stack
fi

# Run layers in order: fast → radius → e2e
# (Docker must be up before radius/e2e if --with-docker)

if [ "$RUN_FAST" = true ]; then
    if ! run_fast; then
        if [ "$CONTINUE_ON_FAILURE" = false ]; then
            # Print report and exit
            docker_stop_stack
            print_report
            exit $OVERALL_EXIT
        fi
    fi
fi

if [ "$RUN_RADIUS" = true ]; then
    if ! run_radius; then
        if [ "$CONTINUE_ON_FAILURE" = false ]; then
            docker_stop_stack
            print_report
            exit $OVERALL_EXIT
        fi
    fi
fi

if [ "$RUN_E2E" = true ]; then
    if ! run_e2e; then
        if [ "$CONTINUE_ON_FAILURE" = false ]; then
            docker_stop_stack
            print_report
            exit $OVERALL_EXIT
        fi
    fi
fi

# Cleanup Docker if we started it
docker_stop_stack

# ─── Final report ────────────────────────────────────────────────────────────
print_report
exit $OVERALL_EXIT
