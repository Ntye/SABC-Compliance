#!/usr/bin/env bash
# =============================================================================
# SABC Compliance — Wazuh agent package fetcher (Debian + RedHat at once)
# =============================================================================
# Downloads the wazuh-agent packages for BOTH package families into the
# platform's packages directory, so the agent install job can run in airgap
# mode against any target OS without touching the internet from the node.
#
#   backend/packages/wazuh-agent/wazuh-agent_<VER>-1_<deb-arch>.deb   (Debian/Ubuntu)
#   backend/packages/wazuh-agent/wazuh-agent-<VER>-1.<rpm-arch>.rpm   (RHEL/Rocky/CentOS/Alma)
#
# RUN ON AN INTERNET-CONNECTED MACHINE (the platform host itself is fine).
#
# Usage:
#   ./deploy/get-wazuh-agents.sh                      # v4.14.6, amd64/x86_64
#   VERSION=4.12.0 ./deploy/get-wazuh-agents.sh       # specific version
#   ARCH=arm64 ./deploy/get-wazuh-agents.sh           # arm64/aarch64 targets
#   ARCH=all ./deploy/get-wazuh-agents.sh             # both architectures
#   OUT_DIR=/some/dir ./deploy/get-wazuh-agents.sh    # custom output dir
#
# NOTE: the agent version must be <= your Wazuh manager version.
# Check the manager: /var/ossec/bin/wazuh-control info | grep version
# =============================================================================
set -euo pipefail

VERSION="${VERSION:-4.14.6}"
ARCH="${ARCH:-amd64}"   # amd64 | arm64 | all
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$SCRIPT_DIR/../backend/packages/wazuh-agent}"
BASE="https://packages.wazuh.com/4.x"

info() { echo -e "\033[1;34m▸\033[0m $*"; }
ok()   { echo -e "\033[1;32m✓\033[0m $*"; }
fail() { echo -e "\033[1;31m✗\033[0m $*"; exit 1; }

command -v curl >/dev/null 2>&1 || fail "curl is required."
case "$ARCH" in amd64|arm64|all) ;; *) fail "ARCH must be amd64, arm64 or all (got '$ARCH')." ;; esac

mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
info "Wazuh agent version : $VERSION"
info "Architectures       : $ARCH"
info "Output directory    : $OUT_DIR"
echo

fetch() { # $1 = url, $2 = dest filename
  local url="$1" dest="$OUT_DIR/$2"
  if [ -s "$dest" ]; then
    ok "already present: $2 ($(du -h "$dest" | cut -f1)) — skipping"
    return 0
  fi
  info "downloading $2 ..."
  # -f: fail on HTTP errors (404 = wrong version); download to .part then move
  if ! curl -fL --connect-timeout 15 --retry 3 -o "$dest.part" "$url"; then
    rm -f "$dest.part"
    fail "download failed: $url
   Check that version $VERSION exists (agent must be <= your manager version)."
  fi
  mv "$dest.part" "$dest"
  ok "saved $2 ($(du -h "$dest" | cut -f1))"
}

want_amd64=false; want_arm64=false
case "$ARCH" in
  amd64) want_amd64=true ;;
  arm64) want_arm64=true ;;
  all)   want_amd64=true; want_arm64=true ;;
esac

# ── Debian / Ubuntu (.deb) ────────────────────────────────────────────────────
$want_amd64 && fetch "$BASE/apt/pool/main/w/wazuh-agent/wazuh-agent_${VERSION}-1_amd64.deb" \
                     "wazuh-agent_${VERSION}-1_amd64.deb"
$want_arm64 && fetch "$BASE/apt/pool/main/w/wazuh-agent/wazuh-agent_${VERSION}-1_arm64.deb" \
                     "wazuh-agent_${VERSION}-1_arm64.deb"

# ── RHEL / Rocky / CentOS / AlmaLinux (.rpm) ─────────────────────────────────
$want_amd64 && fetch "$BASE/yum/wazuh-agent-${VERSION}-1.x86_64.rpm" \
                     "wazuh-agent-${VERSION}-1.x86_64.rpm"
$want_arm64 && fetch "$BASE/yum/wazuh-agent-${VERSION}-1.aarch64.rpm" \
                     "wazuh-agent-${VERSION}-1.aarch64.rpm"

echo
ok "All agent packages are in: $OUT_DIR"
ls -lh "$OUT_DIR" | grep -E "wazuh-agent" || true
echo
info "The agent install job now runs in AIRGAP mode automatically for any"
info "Debian or RedHat target — no internet needed on the nodes."
info "If the platform runs in Docker with a bind-mounted packages dir, the"
info "files are picked up immediately; otherwise redeploy/copy them to the"
info "backend container's /app/packages/wazuh-agent/."
