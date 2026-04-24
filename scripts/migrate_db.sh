#!/bin/bash
# migrate_db.sh - Run Alembic migrations for ZeroRadius backend
# Usage: ./scripts/migrate_db.sh [upgrade|downgrade|current|history|pre-flight]
#
# Environment variables:
#   DATABASE_URL - MySQL connection string (default: mysql+aiomysql://radius:radiuspassword@localhost/radius)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")/backend"

cd "$BACKEND_DIR"

ACTION="${1:-upgrade}"

PYTHON="${PYTHON:-python3}"

echo "Running Alembic migration: $ACTION"

case "$ACTION" in
    upgrade)
        $PYTHON -m alembic upgrade head
        echo "✅ Database upgraded to head"
        ;;
    downgrade)
        TARGET="${2:-base}"
        $PYTHON -m alembic downgrade "$TARGET"
        echo "✅ Database downgraded to $TARGET"
        ;;
    current)
        $PYTHON -m alembic current
        ;;
    history)
        $PYTHON -m alembic history --verbose
        ;;
    pre-flight)
        echo "Running schema pre-flight check..."
        $PYTHON -m alembic upgrade head
        if [ $? -eq 0 ]; then
            echo "✅ Pre-flight check passed — schema is up to date"
        else
            echo "❌ Pre-flight check failed — schema drift detected"
            exit 1
        fi
        ;;
    stamp)
        TARGET="${2:-head}"
        $PYTHON -m alembic stamp "$TARGET"
        echo "✅ Database stamped at $TARGET"
        ;;
    *)
        echo "Usage: $0 {upgrade|downgrade|current|history|pre-flight|stamp}"
        echo ""
        echo "Commands:"
        echo "  upgrade [target]   - Upgrade database (default: head)"
        echo "  downgrade [target] - Downgrade database (default: base)"
        echo "  current            - Show current revision"
        echo "  history            - Show migration history"
        echo "  pre-flight         - Run pre-flight schema check (for deployment)"
        echo "  stamp [target]     - Stamp database at revision without running migrations"
        exit 1
        ;;
esac
