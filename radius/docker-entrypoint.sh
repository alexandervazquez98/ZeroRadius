#!/bin/sh
set -e

# Fix permissions on bind-mounted config files.
# Docker Desktop on Windows mounts files as 0777 (globally writable),
# which causes FreeRADIUS to refuse startup with:
#   "Configuration file ... is globally writable. Refusing to start."
# We copy them to an internal path owned by freerad and use those copies.
for src in \
    /etc/raddb/mods-available/sql \
    /etc/raddb/mods-enabled/sql
do
    if [ -f "$src" ]; then
        chmod 640 "$src" 2>/dev/null || true
        chown freerad:freerad "$src" 2>/dev/null || true
    fi
done

# Also fix any other raddb files that may have landed as 0777
find /etc/raddb -type f -exec chmod go-w {} \; 2>/dev/null || true

# Create a temporary config file for custom dictionary includes
INCLUDE_FILE="/etc/raddb/custom_includes.conf"
echo "# Auto-generated includes for custom dictionaries" > "$INCLUDE_FILE"

# Loop through files in the custom volume and add them to the include file.
# Track already-included paths to avoid duplicates (e.g. when both
# "Cambium 450i" and "Cambium_450i" exist — the space-sanitised copy
# would otherwise be included twice).
INCLUDED_PATHS=""

if [ -d "/etc/raddb/custom_dictionaries" ]; then
    for f in /etc/raddb/custom_dictionaries/*; do
        if [ -f "$f" ]; then
            # Sanitize filename: Replace spaces with underscores
            clean_name=$(basename "$f" | tr ' ' '_')
            clean_path="/etc/raddb/custom_dictionaries/$clean_name"

            # If name changed, copy to sanitised name (unless it already exists)
            if [ "$f" != "$clean_path" ]; then
                if [ -f "$clean_path" ]; then
                    # Sanitised version already exists — skip the space-named duplicate
                    echo "Skipping duplicate dictionary (sanitised version exists): $f"
                    continue
                fi
                cp "$f" "$clean_path"
                f="$clean_path"
            fi

            # Guard against including the same path twice
            case "$INCLUDED_PATHS" in
                *"|$f|"*) echo "Skipping already-included dictionary: $f"; continue ;;
            esac
            INCLUDED_PATHS="${INCLUDED_PATHS}|$f|"

            # Fix permissions (Windows Docker mounts are often 777)
            chmod 644 "$f"

            echo "\$INCLUDE $f" >> "$INCLUDE_FILE"
            echo "Including custom dictionary: $f"
        fi
    done
fi

# Execute the passed command (freeradius -X)
exec "$@"
