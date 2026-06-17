#!/bin/sh
# Dev-server entrypoint: generate a self-signed TLS cert on first launch (so the
# Vite dev server runs over HTTPS — see vite.config.js), then start Vite.
# The cert persists in the /certs volume; delete it to force regeneration.
set -e

# Build the subjectAltName list, appending any hosts from TLS_SAN (comma/space
# separated) so the dev cert is valid for the address nodes use to reach the
# platform (e.g. the public IP), not just localhost.
build_san() {
    san="DNS:localhost,DNS:sabc-compliance,IP:127.0.0.1"
    for h in $(echo "${TLS_SAN:-}" | tr ',' ' '); do
        [ -z "$h" ] && continue
        if echo "$h" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
            san="${san},IP:${h}"
        else
            san="${san},DNS:${h}"
        fi
    done
    echo "$san"
}

if [ ! -f /certs/server.crt ] || [ ! -f /certs/server.key ]; then
    echo "[dev-entrypoint] Generating self-signed TLS certificate (SAN=$(build_san))…"
    apk add --no-cache openssl >/dev/null 2>&1
    mkdir -p /certs
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /certs/server.key -out /certs/server.crt \
        -subj "/CN=sabc-compliance" \
        -addext "subjectAltName=$(build_san)" >/dev/null 2>&1
    echo "[dev-entrypoint] Certificate written to /certs/server.crt"
fi

npm install
exec npm run dev -- --host 0.0.0.0
