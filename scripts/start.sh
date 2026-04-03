#!/usr/bin/env bash
#
# ZeroRadius — cross-platform Docker Compose launcher
#
# Auto-detects the OS and applies the correct compose override:
#   Linux  → docker-compose.linux.yml  (host networking for radius)
#   Other  → docker-compose.yml only   (bridge networking)
#
# Usage:
#   ./scripts/start.sh up -d
#   ./scripts/start.sh logs -f radius
#   ./scripts/start.sh ps
#   ./scripts/start.sh down
#

set -euo pipefail

# Resolve the project root (parent directory of scripts/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Build compose file array
COMPOSE_FILES=(-f docker-compose.yml)

# Auto-detect platform
OS="$(uname -s)"

if [[ "$OS" == "Linux" ]]; then
    COMPOSE_FILES+=(-f docker-compose.linux.yml)
    echo "🐧 Linux detected — using host networking for radius-server"
else
    echo "🖥️ ${OS} detected — using bridge networking (default)"
fi

# Execute docker compose with the resolved file list
docker compose "${COMPOSE_FILES[@]}" "$@"
