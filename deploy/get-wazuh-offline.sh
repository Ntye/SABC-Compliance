#!/usr/bin/env bash
# =============================================================================
# SABC Compliance — Wazuh offline (airgap) bundle builder + verifier
# =============================================================================
# Follows the OFFICIAL Wazuh offline installation procedure exactly, then VERIFIES
# the bundle contains every package the installer needs (wazuh-manager,
# wazuh-indexer, wazuh-dashboard, filebeat) before you ship it. The recurring
# "Missing necessary offline file: …/filebeat_*.deb" failures come from bundles
# built WITHOUT the architecture flag (-da amd64) or on the wrong OS; this script
# uses the correct flags and refuses to produce an incomplete bundle.
#
# Produces the three files the platform (and Wazuh) need for an all-in-one
# offline install:
#   wazuh-install.sh          the installation assistant
#   wazuh-offline.tar.gz      all packages (renamed wazuh-offline-<deb|rpm>.tar.gz)
#   wazuh-install-files.tar   certificates, pre-generated for 127.0.0.1 (all-in-one)
#
# RUN ON AN INTERNET-CONNECTED MACHINE OF THE SAME OS FAMILY + ARCH AS THE TARGET
# (Ubuntu/Debian x86_64 target → build on Ubuntu/Debian x86_64), as root.
#
# Usage:
#   sudo ./deploy/get-wazuh-offline.sh                 # v4.14, auto OS+arch, all-in-one
#   sudo VERSION=4.14 ./deploy/get-wazuh-offline.sh
#
# Reference: https://documentation.wazuh.com/current/deployment-options/offline-installation.html
# =============================================================================
set -euo pipefail

VERSION="${VERSION:-4.14}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="${OUT_DIR:-$SCRIPT_DIR/wazuh-manager}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

info() { echo -e "\033[1;34m▸\033[0m $*"; }
ok()   { echo -e "\033[1;32m✓\033[0m $*"; }
fail() { echo -e "\033[1;31m✗\033[0m $*"; exit 1; }

[ "$(id -u)" -eq 0 ] || fail "Run as root (sudo) — the Wazuh downloader and cert generation need it."

# ── Detect package format + Wazuh's architecture name ────────────────────────
if   command -v apt-get >/dev/null 2>&1; then PKG="deb"
elif command -v yum >/dev/null 2>&1 || command -v dnf >/dev/null 2>&1; then PKG="rpm"
else fail "Unsupported OS: need apt (Debian/Ubuntu) or yum/dnf (RHEL family)."; fi

case "$(uname -m)" in
  x86_64|amd64)   DA="amd64" ;;
  aarch64|arm64)  DA="arm64" ;;
  *) fail "Unsupported arch $(uname -m) — Wazuh offline supports amd64 or arm64." ;;
esac
info "Building Wazuh ${VERSION} OFFLINE bundle: format=${PKG}, arch=${DA}"

# The build host's prerequisites (per the official guide) — needed by -g too.
info "Ensuring build-host prerequisites (curl, tar, gnupg, setcap) ..."
if [ "$PKG" = "deb" ]; then
  apt-get update -y >/dev/null 2>&1 || true
  apt-get install -y curl tar gnupg libcap2-bin >/dev/null 2>&1 || true
else
  ( yum install -y curl tar gnupg2 libcap >/dev/null 2>&1 || dnf install -y curl tar gnupg2 libcap >/dev/null 2>&1 ) || true
fi

cd "$WORK"

# ── 1. Installation assistant ────────────────────────────────────────────────
info "Downloading wazuh-install.sh (${VERSION}) ..."
curl -sO "https://packages.wazuh.com/${VERSION}/wazuh-install.sh" \
  || fail "Could not download wazuh-install.sh — online? version ${VERSION} valid?"
chmod 744 wazuh-install.sh

# ── 2. Download all packages for THIS format + arch (the -da flag matters!) ──
info "Downloading all packages: ./wazuh-install.sh -dw ${PKG} -da ${DA} (~1.6 GB) ..."
bash wazuh-install.sh -dw "${PKG}" -da "${DA}" 2>&1 | tail -20 \
  || fail "Package download failed — see output above."
[ -f wazuh-offline.tar.gz ] || fail "wazuh-offline.tar.gz was not produced by -dw."

# ── 3-5. Certificates config + generation (all-in-one → 127.0.0.1) ───────────
info "Downloading config.yml and preparing an all-in-one (127.0.0.1) layout ..."
curl -sO "https://packages.wazuh.com/${VERSION}/config.yml" \
  || fail "Could not download config.yml."
# Replace every "<...-node-ip>" / "<wazuh-manager-ip>" placeholder with 127.0.0.1.
sed -i -E 's/"<[^"]*>"/"127.0.0.1"/g' config.yml

info "Generating certificates: ./wazuh-install.sh -g ..."
bash wazuh-install.sh -g 2>&1 | tail -10 || fail "Certificate generation (-g) failed."
[ -f wazuh-install-files.tar ] || fail "wazuh-install-files.tar (certs) was not produced by -g."

# ── 6. VERIFY the bundle is complete for this OS ─────────────────────────────
info "Verifying wazuh-offline.tar.gz contains all required ${PKG} packages ..."
listing="$(tar tzf wazuh-offline.tar.gz)"
missing=""
for want in wazuh-manager wazuh-indexer wazuh-dashboard filebeat; do
  printf '%s\n' "$listing" | grep -Eq "wazuh-packages/.*${want}.*\.${PKG}\$" || missing="${missing} ${want}"
done
if [ -n "$missing" ]; then
  echo "  Packages present in the bundle:"
  printf '%s\n' "$listing" | grep -E "wazuh-packages/.*\.(deb|rpm)$" | sed 's/^/    /' || true
  fail "Bundle INCOMPLETE — missing:${missing}. Do NOT ship it. (Built on the wrong OS/arch?)"
fi
ok "Bundle verified — manager, indexer, dashboard and filebeat (${PKG}/${DA}) all present."

# ── Place the three files, ready to ship ─────────────────────────────────────
mkdir -p "$OUT_DIR"
cp wazuh-offline.tar.gz    "$OUT_DIR/wazuh-offline-${PKG}.tar.gz"
cp wazuh-install-files.tar "$OUT_DIR/wazuh-install-files.tar"
cp wazuh-install.sh        "$OUT_DIR/wazuh-install.sh"
size="$(du -h "$OUT_DIR/wazuh-offline-${PKG}.tar.gz" | cut -f1)"
ok "Wrote to $OUT_DIR: wazuh-offline-${PKG}.tar.gz (${size}), wazuh-install-files.tar, wazuh-install.sh"

cat <<EOF

──────────────────────────────────────────────────────────────────────────────
 Airgap bundle ready (all-in-one, certs for 127.0.0.1). Copy the THREE files to
 the platform's packages dir:

   scp $OUT_DIR/wazuh-offline-${PKG}.tar.gz \\
       $OUT_DIR/wazuh-install-files.tar \\
       $OUT_DIR/wazuh-install.sh \\
       user@platform:/opt/sabc-compliance/backend/packages/wazuh-manager/

 IMPORTANT — the AIRGAP TARGET also needs curl, tar, setcap (libcap2-bin) and
 gnupg pre-installed (the offline installer requires them and cannot fetch them
 with no internet). On the target once, before going airgapped:
   sudo apt-get install -y curl tar libcap2-bin gnupg      # Debian/Ubuntu
   sudo yum install -y curl tar libcap gnupg2              # RHEL family

 Then run the Wazuh manager install from the platform — it detects
 wazuh-offline-${PKG}.tar.gz and installs fully offline.
──────────────────────────────────────────────────────────────────────────────
EOF
