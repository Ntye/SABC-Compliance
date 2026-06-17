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

# ── Auto-detect public IP when TLS_SAN was not supplied ──────────────────────
# Covers the common case where PLATFORM_PUBLIC_HOST is not set in .env: the
# platform's public IP is discovered automatically so https://<ip>:<port> works
# without any manual configuration.
# Precedence: EC2 IMDSv2 → IMDSv1 → hostname -I (first non-loopback address).
if [ -z "${TLS_SAN:-}" ]; then
    _auto_ip=""
    # IMDSv2 (required on instances with IMDSv2 enforced)
    _token=$(curl -sf --connect-timeout 2 -X PUT \
        "http://169.254.169.254/latest/api/token" \
        -H "X-aws-ec2-metadata-token-ttl-seconds: 10" 2>/dev/null || true)
    if [ -n "$_token" ]; then
        _auto_ip=$(curl -sf --connect-timeout 2 \
            -H "X-aws-ec2-metadata-token: $_token" \
            "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
    fi
    # IMDSv1 fallback
    if [ -z "$_auto_ip" ]; then
        _auto_ip=$(curl -sf --connect-timeout 2 \
            "http://169.254.169.254/latest/meta-data/public-ipv4" 2>/dev/null || true)
    fi
    # Non-EC2 fallback: first address reported by hostname -I
    if [ -z "$_auto_ip" ]; then
        _auto_ip=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    fi
    if [ -n "$_auto_ip" ]; then
        TLS_SAN="$_auto_ip"
        echo "[tls-entrypoint] Auto-detected host IP: $_auto_ip (added to cert SAN)"
    fi
fi

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

# ── Hot-reload watcher ───────────────────────────────────────────────────────
# The backend can install a CA-signed cert into this shared volume from the UI
# (POST /api/settings/tls/certificate). Poll the cert file and reload nginx when
# it changes so the new certificate takes effect without a container restart.
# `nginx -t` gates the reload: a bad cert is never loaded, so the running server
# keeps serving the previous (working) certificate.
watch_cert_and_reload() {
    last="$(md5sum "$CERT" 2>/dev/null | awk '{print $1}')"
    while true; do
        sleep 5
        [ -f "$CERT" ] || continue
        cur="$(md5sum "$CERT" 2>/dev/null | awk '{print $1}')"
        if [ -n "$cur" ] && [ "$cur" != "$last" ]; then
            last="$cur"
            if nginx -t >/dev/null 2>&1; then
                nginx -s reload && echo "[tls-entrypoint] Certificate changed — nginx reloaded with the new cert."
            else
                echo "[tls-entrypoint] Certificate changed but failed nginx -t — keeping the previous cert."
            fi
        fi
    done
}
watch_cert_and_reload &

exec nginx -g 'daemon off;'
