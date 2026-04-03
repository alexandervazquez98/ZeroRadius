#!/bin/bash
# migrate_db.sh - Run Alembic migrations for ZeroRadius backend
# Usage: ./scripts/migrate_db.sh [upgrade|downgrade|current|history]
#
# Environment variables:
#   DATABASE_URL - MySQL connection string (default: mysql+aiomysql://radius:radiuspassword@localhost/radius)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

cd "$BACKEND_DIR"

ACTION="${1:-upgrade}"

echo "Running Alembic migration: $ACTION"

case "$ACTION" in
    upgrade)
        python3.13 -m alembic upgrade head
        echo "✅ Database upgraded to head"
        ;;
    downgrade)
        TARGET="${2:-base}"
        python3.13 -m alembic downgrade "$TARGET"
        echo "✅ Database downgraded to $TARGET"
        ;;
    current)
        python3.13 -m alembic current
        ;;
    history)
        python3.13 -m alembic history --verbose
        ;;
    stamp)
        TARGET="${2:-head}"
        python3.13 -m alembic stamp "$TARGET"
        echo "✅ Database stamped at $TARGET"
        ;;
    *)
        echo "Usage: $0 {upgrade|downgrade|current|history|stamp}"
        echo ""
        echo "Commands:"
        echo "  upgrade [target]   - Upgrade database (default: head)"
        echo "  downgrade [target] - Downgrade database (default: base)"
        echo "  current            - Show current revision"
        echo "  history            - Show migration history"
        echo "  stamp [target]     - Stamp database at revision without running migrations"
        exit 1
        ;;
esac
