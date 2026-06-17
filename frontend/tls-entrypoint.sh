#!/bin/sh
# Generate a self-signed TLS certificate on first launch, then start Nginx.
# The cert lives in a Docker volume (/etc/nginx/certs) so it persists across
# container replacements. To use a CA-signed certificate instead, drop your
# own server.crt / server.key into that volume — this script leaves an
# externally-supplied (CA-signed) certificate untouched.
set -e

CERT_DIR=/etc/nginx/certs
CERT="$CERT_DIR/server.crt"
KEY="$CERT_DIR/server.key"
CN="${TLS_CN:-sabc-compliance}"

mkdir -p "$CERT_DIR"

# Build the subjectAltName list. Always include localhost + the CN + loopback.
# TLS_SAN carries additional hosts (e.g. the platform's public IP or DNS name)
# as a comma- or space-separated list, so the self-signed cert is valid for the
# address nodes actually use to reach the platform — e.g. https://<public-ip>:8443.
# Without this, an IP-based HTTPS URL fails the SAN check even after the cert
# is trusted.
build_san() {
    san="DNS:localhost,DNS:${CN},IP:127.0.0.1"
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

# Does the existing cert already cover every host listed in TLS_SAN?
cert_covers_san() {
    [ -f "$CERT" ] || return 1
    existing="$(openssl x509 -in "$CERT" -noout -text 2>/dev/null || true)"
    for h in $(echo "${TLS_SAN:-}" | tr ',' ' '); do
        [ -z "$h" ] && continue
        echo "$existing" | grep -qF "$h" || return 1
    done
    return 0
}

# Is the existing cert self-signed (issuer == subject)? We only ever regenerate
# our OWN self-signed cert — a CA-signed cert dropped in by the operator is
# always left untouched, even if it lacks a TLS_SAN host.
cert_is_self_signed() {
    [ -f "$CERT" ] || return 1
    subj="$(openssl x509 -in "$CERT" -noout -subject 2>/dev/null | sed 's/^subject=//')"
    iss="$(openssl x509 -in "$CERT" -noout -issuer 2>/dev/null | sed 's/^issuer=//')"
    [ -n "$subj" ] && [ "$subj" = "$iss" ]
}

gen_cert() {
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$KEY" -out "$CERT" \
        -subj "/CN=$CN" \
        -addext "subjectAltName=$(build_san)"
}

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "[tls-entrypoint] No certificate found — generating a self-signed cert (CN=$CN, SAN=$(build_san), 10y)…"
    gen_cert
    echo "[tls-entrypoint] Certificate written to $CERT"
elif cert_is_self_signed && ! cert_covers_san; then
    echo "[tls-entrypoint] Self-signed cert is missing a required SAN host — regenerating (SAN=$(build_san))…"
    gen_cert
    echo "[tls-entrypoint] Certificate regenerated at $CERT"
else
    echo "[tls-entrypoint] Existing certificate is valid for the required hosts — leaving it untouched."
fi

exec nginx -g 'daemon off;'
