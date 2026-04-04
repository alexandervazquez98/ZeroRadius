#!/usr/bin/env bash
#
# ZeroRadius — Frontend fast tests (Vitest)
#
# Runs frontend component/unit tests using local node_modules.
# Works from Git Bash on Windows, WSL, Linux, and macOS.
#
# Usage:
#   ./scripts/test-frontend-fast.sh            # run all tests
#   ./scripts/test-frontend-fast.sh --coverage # with coverage report
#   ./scripts/test-frontend-fast.sh -- src/LoginPage.test.jsx  # single file
#
# Prerequisites:
#   - frontend/node_modules exists (npm install / npm ci already run)
#   - Run from the project root or this script will cd there
#

set -euo pipefail

# Resolve the project root (parent directory of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

FRONTEND_DIR="$PROJECT_ROOT/frontend"
VITEST_BIN="$FRONTEND_DIR/node_modules/.bin/vitest"

# Verify node_modules exists
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "ERROR: frontend/node_modules not found."
    echo "Install dependencies first:  cd frontend && npm install"
    exit 1
fi

echo "[test-frontend] Running Vitest in frontend/ ..."

# Detect OS to choose the correct invocation
OS="$(uname -s)"

if [[ "$OS" == MINGW* ]] || [[ "$OS" == MSYS* ]] || [[ "$OS" == CYGWIN* ]]; then
    # Windows (Git Bash / MSYS2 / Cygwin)
    # Use cmd /c with the .cmd wrapper — avoids PowerShell execution policy
    # and bash-script incompatibility issues.
    VITEST_ARGS="run"

    if [ $# -gt 0 ]; then
        if [ "$1" = "--coverage" ]; then
            VITEST_ARGS="$VITEST_ARGS --coverage"
            shift
        fi
        # Append remaining args (e.g. specific test files)
        for arg in "$@"; do
            VITEST_ARGS="$VITEST_ARGS $arg"
        done
    fi

    echo "[test-frontend] Platform: Windows (cmd wrapper)"
    echo "[test-frontend] Args: $VITEST_ARGS"

    cd "$FRONTEND_DIR"
    cmd //c "node_modules\\.bin\\vitest.cmd $VITEST_ARGS"
else
    # Unix / Linux / macOS
    VITEST_ARGS=("run")

    if [ $# -gt 0 ]; then
        if [ "$1" = "--coverage" ]; then
            VITEST_ARGS+=("--coverage")
            shift
        fi
        VITEST_ARGS+=("$@")
    fi

    echo "[test-frontend] Platform: ${OS}"
    echo "[test-frontend] Args: ${VITEST_ARGS[*]}"

    cd "$FRONTEND_DIR"
    "$VITEST_BIN" "${VITEST_ARGS[@]}"
fi
