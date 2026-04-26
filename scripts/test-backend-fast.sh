#!/usr/bin/env bash
#
# ZeroRadius — Backend fast tests (pytest, no RADIUS, no infra)
#
# Runs backend unit + integration tests using the project virtualenv
# (backend/.venv).  Skips RADIUS and infrastructure-dependent tests by default.
#
# Usage:
#   ./scripts/test-backend-fast.sh          # all fast tests
#   ./scripts/test-backend-fast.sh --no-cov # skip coverage for speed
#   ./scripts/test-backend-fast.sh tests/unit/  # specific path
#
# Prerequisites:
#   - backend/.venv exists with dependencies installed
#   - Run from the project root or this script will cd there
#

set -euo pipefail

# Resolve the project root (parent directory of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

VENV_DIR="$PROJECT_ROOT/backend/.venv"

# Verify virtualenv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "ERROR: backend/.venv not found."
    echo "Create it first:  cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt -r requirements-test.txt"
    exit 1
fi

# Activate virtualenv
VENV_ACTIVATE="$VENV_DIR/bin/activate"
if [ -f "$VENV_ACTIVATE" ]; then
    # Unix / Git Bash
    source "$VENV_ACTIVATE"
else
    VENV_ACTIVATE="$VENV_DIR/Scripts/activate"
    if [ -f "$VENV_ACTIVATE" ]; then
        # Windows Git Bash (MSYS2 path)
        source "$VENV_ACTIVATE"
    else
        echo "ERROR: Cannot find activate script in $VENV_DIR"
        echo "Expected: bin/activate or Scripts/activate"
        exit 1
    fi
fi

# Load test environment defaults: .env.test.example first, then overlay .env.test
ENV_DEFAULTS="$PROJECT_ROOT/.env.test.example"
ENV_TEST="$PROJECT_ROOT/.env.test"

set -a
if [ -f "$ENV_DEFAULTS" ]; then
    # shellcheck disable=SC1090
    source "$ENV_DEFAULTS"
fi
if [ -f "$ENV_TEST" ]; then
    # Overlay local overrides (takes precedence over defaults)
    # shellcheck disable=SC1090
    source "$ENV_TEST"
    echo "[test-backend] Loaded .env.test overrides"
fi
set +a

# Build pytest command
PYTEST_ARGS=()

# Default: skip RADIUS and infrastructure (certs, Docker, Linux-specific) tests
PYTEST_ARGS+=("-m" "not radius and not infra")

# Determine test target: user-provided path(s) or full suite
TEST_TARGET=""

# Allow user overrides via arguments
if [ $# -gt 0 ]; then
    # If user passed --no-cov as first arg, add it and shift
    if [ "$1" = "--no-cov" ]; then
        PYTEST_ARGS+=("--no-cov")
        shift
    fi
    # If remaining args look like test paths (not flags), use them as target
    if [ $# -gt 0 ] && [[ "$1" != --* ]]; then
        TEST_TARGET="$*"
    fi
fi

echo "[test-backend] Running pytest in backend/ ..."
echo "[test-backend] Args: ${PYTEST_ARGS[*]}"
if [ -n "$TEST_TARGET" ]; then
    echo "[test-backend] Target: $TEST_TARGET"
    cd "$PROJECT_ROOT/backend"
    python -m pytest $TEST_TARGET "${PYTEST_ARGS[@]}" -v
else
    echo "[test-backend] Target: tests/ (full suite)"
    cd "$PROJECT_ROOT/backend"
    python -m pytest tests/ "${PYTEST_ARGS[@]}" -v
fi
