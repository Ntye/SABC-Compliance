#!/bin/sh
# Dev-server entrypoint: generate a self-signed TLS cert on first launch (so the
# Vite dev server runs over HTTPS — see vite.config.js), then start Vite.
# The cert persists in the /certs volume; delete it to force regeneration.
set -e

if [ ! -f /certs/server.crt ] || [ ! -f /certs/server.key ]; then
    echo "[dev-entrypoint] Generating self-signed TLS certificate…"
    apk add --no-cache openssl >/dev/null 2>&1
    mkdir -p /certs
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /certs/server.key -out /certs/server.crt \
        -subj "/CN=sabc-compliance" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
    echo "[dev-entrypoint] Certificate written to /certs/server.crt"
fi

npm install
exec npm run dev -- --host 0.0.0.0
