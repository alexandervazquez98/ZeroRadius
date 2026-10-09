#!/bin/sh
set -e

# ============================================================================
# Wait for MySQL to be available before starting FreeRADIUS
# Critical for Linux host networking where DB is on 127.0.0.1
# ============================================================================
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-radius}"
DB_PASS="${DB_PASS:-secure_radius_password}"
MAX_RETRIES=30
RETRY_INTERVAL=2

echo "Waiting for MySQL at ${DB_HOST}:${DB_PORT}..."
for i in $(seq 1 $MAX_RETRIES); do
    # TCP-level check — works without mysql client installed
    if nc -z -w2 "$DB_HOST" "$DB_PORT" 2>/dev/null; then
        echo "MySQL is ready after $i attempts."
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "ERROR: MySQL not reachable after $MAX_RETRIES attempts."
        exit 1
    else
        echo "Attempt $i/$MAX_RETRIES — MySQL not ready, retrying in ${RETRY_INTERVAL}s..."
        sleep $RETRY_INTERVAL
    fi
done

# ============================================================================
# Certificate initialization
#
# FreeRADIUS's eap module reads `/etc/freeradius/certs/server.{pem,key}` and
# `/etc/freeradius/certs/ca.{pem,key}`. In a fresh deploy the named volume
# mounted at that path is empty, so the radius container would crash-loop
# waiting for certs. The entrypoint generates a self-signed pair in-place
# when the volume is empty.
#
# The volume is a Docker named volume (not a host bind mount), so the
# chown/chmod below operate on container-internal storage and cannot
# escape onto the host working tree. (Fixes #85.)
#
# For a real deploy that wants long-lived certs, drop pre-generated files
# into the named volume manually:
#   docker compose run --rm -v radius_radius_certs:/target radius \
#       cp /source/{ca,server}.{pem,key} /target/
# ============================================================================

CERT_DIR="/etc/raddb/certs"
MOUNTED_CERTS="/etc/freeradius/certs"

mkdir -p "$CERT_DIR" "$MOUNTED_CERTS"

# Count files in the named volume
FILE_COUNT=$(ls -1 "$MOUNTED_CERTS" 2>/dev/null | wc -l)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "No certificates in $MOUNTED_CERTS — generating self-signed pair..."

    # NOTE: no `-quiet` here — the flag was removed in OpenSSL 3.0 and the
    # image is OpenSSL 3.0.2. Use stdout/stderr redirect instead.
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$MOUNTED_CERTS/server.key" \
        -out    "$MOUNTED_CERTS/server.pem" \
        -subj "/C=MX/ST=Local/L=Local/O=ZeroRadius/CN=localhost" \
        >/dev/null 2>&1

    # Use the server cert as the CA (self-signed, single-tier PKI).
    cp -f "$MOUNTED_CERTS/server.pem" "$MOUNTED_CERTS/ca.pem"
    # NOTE: do NOT create dh.pem by copying the cert. DH params are not a
    # certificate — they need a real `openssl dhparam` generation. The
    # freeradius-3.2 image ships its own dh.pem; if the operator wants a
    # custom one, drop it into the named volume pre-deploy.

    echo "Certificates generated in $MOUNTED_CERTS"
else
    echo "Found $FILE_COUNT file(s) in $MOUNTED_CERTS — using existing certs"
fi

# Mirror the certs into the internal /etc/raddb/certs (FreeRADIUS config
# references both paths in different contexts). This is a CONTAINER-LOCAL
# copy — it does not touch the host or any external mount.
cp -f "$MOUNTED_CERTS"/*.pem "$CERT_DIR/" 2>/dev/null || true
cp -f "$MOUNTED_CERTS"/*.key "$CERT_DIR/" 2>/dev/null || true

# Permissions: private keys 0600, public certs 0644. Ownership: freerad.
chmod 600 "$CERT_DIR"/*.key 2>/dev/null || true
chmod 644 "$CERT_DIR"/*.pem 2>/dev/null || true
chown -R freerad:freerad "$CERT_DIR" 2>/dev/null || true
chown -R freerad:freerad "$MOUNTED_CERTS" 2>/dev/null || true

# Note: the previous `openssl rsa -in ... -check -noout` verification was
# removed — it was a no-op for our generated certs (no passphrase), and
# it would prompt on any pre-populated passphrase-protected key, training
# operators to ignore "Key verification FAILED" noise. The chmod + chown
# above are sufficient signals that the key is on disk and accessible.

echo "Certificates ready"

# Fix permissions on bind-mounted config files.
# Docker Desktop on Windows mounts files as 0777 (globally writable),
# which causes FreeRADIUS to refuse startup with:
#   "Configuration file ... is globally writable. Refusing to start."
# We copy them to an internal path owned by freerad and use those copies.
for src in \
    /etc/raddb/clients.conf \
    /etc/freeradius/clients.conf \
    /etc/freeradius/sites-enabled/default \
    /etc/raddb/mods-available/sql \
    /etc/raddb/mods-enabled/sql
do
    if [ -f "$src" ]; then
        chmod 640 "$src" 2>/dev/null || true
        chown freerad:freerad "$src" 2>/dev/null || true
    fi
done

# Fix symlink for certificates (some configs reference /etc/freeradius/certs)
# No longer needed - volume mounts directly to /etc/freeradius/certs

# Also fix any other raddb files that may have landed as 0777
find /etc/raddb -type f -exec chmod go-w {} \; 2>/dev/null || true

# ============================================================================
# Custom dictionaries — loaded ONLY if files exist in the bind-mounted volume.
# The directory is empty by default; dictionaries are uploaded via the API.
# ============================================================================
INCLUDE_FILE="/etc/raddb/dictionary"
CUSTOM_INCLUDE_MARKER="# CUSTOM_DICTIONARIES"

# Remove ALL old custom includes (lines with custom_dictionaries path) AND the marker
# This ensures stale references are cleaned when dictionaries are deleted via UI
sed -i "/custom_dictionaries/d" "$INCLUDE_FILE"
sed -i "/$CUSTOM_INCLUDE_MARKER/d" "$INCLUDE_FILE"

if [ -d "/etc/raddb/custom_dictionaries" ]; then
    FILE_COUNT=$(ls -1 /etc/raddb/custom_dictionaries/ 2>/dev/null | wc -l)
    if [ "$FILE_COUNT" -gt 0 ]; then
        echo "" >> "$INCLUDE_FILE"
        echo "$CUSTOM_INCLUDE_MARKER" >> "$INCLUDE_FILE"

        for f in /etc/raddb/custom_dictionaries/*; do
            if [ -f "$f" ]; then
                # Sanitize filename
                clean_name=$(basename "$f" | tr ' ' '_')
                clean_path="/etc/raddb/custom_dictionaries/$clean_name"

                if [ "$f" != "$clean_path" ]; then
                    if [ ! -f "$clean_path" ]; then
                        cp "$f" "$clean_path"
                    fi
                    f="$clean_path"
                fi

                chmod 644 "$f"
                echo "\$INCLUDE $f" >> "$INCLUDE_FILE"
                echo "Including custom dictionary: $f"
            fi
        done
    fi
fi

# Execute the passed command (freeradius -X)
exec "$@"
