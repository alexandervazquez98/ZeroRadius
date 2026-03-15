#!/bin/sh
set -e

CERT_DIR=/etc/nginx/certs

if [ ! -f "$CERT_DIR/nginx.crt" ] || [ ! -f "$CERT_DIR/nginx.key" ]; then
    echo "[entrypoint] Certificates not found — generating self-signed..."
    mkdir -p "$CERT_DIR"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$CERT_DIR/nginx.key" \
        -out    "$CERT_DIR/nginx.crt" \
        -subj "/C=MX/ST=Local/L=Local/O=ZeroRadius/CN=localhost" \
        -quiet
    echo "[entrypoint] Certificates generated."
else
    echo "[entrypoint] Certificates already present — skipping generation."
fi

exec "$@"
