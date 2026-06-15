#!/bin/sh
# Generate a self-signed TLS certificate on first launch, then start Nginx.
# The cert lives in a Docker volume (/etc/nginx/certs) so it persists across
# container replacements. To use a CA-signed certificate instead, drop your
# own server.crt / server.key into that volume — this script leaves existing
# files untouched.
set -e

CERT_DIR=/etc/nginx/certs
CERT="$CERT_DIR/server.crt"
KEY="$CERT_DIR/server.key"
CN="${TLS_CN:-sabc-compliance}"

mkdir -p "$CERT_DIR"

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[tls-entrypoint] No certificate found — generating a self-signed cert (CN=$CN, 10y)…"
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$KEY" -out "$CERT" \
        -subj "/CN=$CN" \
        -addext "subjectAltName=DNS:localhost,DNS:$CN,IP:127.0.0.1"
    echo "[tls-entrypoint] Certificate written to $CERT"
else
    echo "[tls-entrypoint] Existing certificate found at $CERT — leaving it untouched."
fi

exec nginx -g 'daemon off;'
