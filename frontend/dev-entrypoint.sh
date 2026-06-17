#!/bin/sh
# Dev-server entrypoint: generate a self-signed TLS cert on first launch (so the
# Vite dev server runs over HTTPS — see vite.config.js), then start Vite.
# The cert persists in the /certs volume; delete it to force regeneration.
set -e

# Install dependencies upfront (openssl for cert generation, curl for IP detection).
apk add --no-cache openssl curl >/dev/null 2>&1

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

# Auto-detect public IP when TLS_SAN was not supplied (same logic as tls-entrypoint.sh).
if [ -z "${TLS_SAN:-}" ]; then
    _auto_ip=""
    _token=$(curl -sf --connect-timeout 2 -X PUT \
        "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 10" 2>/dev/null || true)
    if [ -n "$_token" ]; then
        _auto_ip=$(curl -sf --connect-timeout 2 \
            -H "X-aws-ec2-metadata-token: $_token" \
            "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
    fi
    if [ -z "$_auto_ip" ]; then
        _auto_ip=$(curl -sf --connect-timeout 2 \
            "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
    fi
    if [ -z "$_auto_ip" ]; then
        _auto_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    fi
    if [ -n "$_auto_ip" ]; then
        TLS_SAN="$_auto_ip"
        echo "[dev-entrypoint] Auto-detected host IP: $_auto_ip (added to cert SAN)"
    fi
fi

if [ ! -f /certs/server.crt ] || [ ! -f /certs/server.key ]; then
    echo "[dev-entrypoint] Generating self-signed TLS certificate (SAN=$(build_san))…"
    mkdir -p /certs
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout /certs/server.key -out /certs/server.crt \
        -subj "/CN=sabc-compliance" \
        -addext "subjectAltName=$(build_san)" >/dev/null 2>&1
    echo "[dev-entrypoint] Certificate written to /certs/server.crt"
fi

npm install
exec npm run dev -- --host 0.0.0.0
