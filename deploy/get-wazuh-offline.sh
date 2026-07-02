#!/usr/bin/env bash
# =============================================================================
# SABC Compliance — Wazuh offline bundle builder (+ verifier)
# =============================================================================
# Builds a COMPLETE Wazuh offline installation bundle for an airgapped install,
# and — crucially — VERIFIES it contains every package the installer needs
# (wazuh-manager, wazuh-indexer, wazuh-dashboard, filebeat) before you ship it.
# The "Missing necessary offline file: …/filebeat_*.deb" failures come from
# incomplete/wrong-OS bundles; this script refuses to produce one.
#
# RUN THIS ON AN INTERNET-CONNECTED MACHINE OF THE SAME OS FAMILY + ARCH AS THE
# AIRGAPPED TARGET:
#   * target is Ubuntu/Debian x86_64  → run on Ubuntu/Debian x86_64  (builds .deb)
#   * target is RHEL/Rocky/Alma x86_64 → run on a RHEL-family x86_64  (builds .rpm)
# Package type and arch are baked into the bundle, so a mismatch will fail on the
# target — build on a matching box.
#
# Usage:
#   sudo ./deploy/get-wazuh-offline.sh                 # version 4.14, auto OS
#   sudo VERSION=4.14 ./deploy/get-wazuh-offline.sh    # pin the Wazuh version
#
# Output: deploy/wazuh-manager/wazuh-offline-<deb|rpm>.tar.gz  (+ wazuh-install.sh)
# Then copy that whole directory into the platform's packages dir on the server:
#   backend/packages/wazuh-manager/   (or /opt/sabc-compliance/backend/packages/wazuh-manager/)
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

# ── Detect OS family → package type ──────────────────────────────────────────
if command -v apt-get >/dev/null 2>&1; then
  PKG="deb"
elif command -v yum >/dev/null 2>&1 || command -v dnf >/dev/null 2>&1; then
  PKG="rpm"
else
  fail "Unsupported OS: need apt (Debian/Ubuntu) or yum/dnf (RHEL family)."
fi
ARCH="$(uname -m)"
[ "$(id -u)" -eq 0 ] || fail "Run as root (sudo) — the Wazuh downloader needs it."
info "Building a Wazuh ${VERSION} OFFLINE bundle: type=${PKG}, arch=${ARCH}"
[ "$ARCH" = "x86_64" ] || echo "  ! arch is ${ARCH}; ensure it matches your target."

cd "$WORK"

# ── 1. Fetch the installation assistant for this version ─────────────────────
info "Downloading wazuh-install.sh (${VERSION}) ..."
curl -fsSL -o wazuh-install.sh "https://packages.wazuh.com/${VERSION}/wazuh-install.sh" \
  || fail "Could not download wazuh-install.sh — is this machine online / version ${VERSION} valid?"
chmod +x wazuh-install.sh

# ── 2. Determine the correct 'download resources' flag from the assistant ────
# Wazuh has used -dw/--download-resources (current) and --download-packages
# across versions. Detect whichever this assistant actually supports.
if grep -q -- '--download-resources' wazuh-install.sh; then
  DL_FLAG="-dw"
elif grep -q -- '--download-packages' wazuh-install.sh; then
  DL_FLAG="--download-packages"
else
  fail "This wazuh-install.sh has no recognised offline-download option; check 'bash wazuh-install.sh -h'."
fi
info "Using download flag: ${DL_FLAG}"

# ── 3. Build the offline bundle ──────────────────────────────────────────────
info "Downloading all Wazuh ${VERSION} ${PKG} packages (this pulls ~1.6 GB) ..."
# Newer assistants ignore a trailing type arg; older need it. Try with the type,
# fall back to bare flag.
bash wazuh-install.sh ${DL_FLAG} "${PKG}" 2>&1 | tail -20 \
  || bash wazuh-install.sh ${DL_FLAG} 2>&1 | tail -20 \
  || fail "wazuh-install.sh ${DL_FLAG} failed — see output above."

# Locate the produced tarball (name has varied: wazuh-offline.tar.gz).
BUNDLE="$(ls -1 wazuh-offline*.tar.gz 2>/dev/null | head -1 || true)"
[ -n "$BUNDLE" ] || fail "No wazuh-offline*.tar.gz was produced by the download step."

# ── 4. VERIFY the bundle is complete for this OS ─────────────────────────────
info "Verifying the bundle contains all required ${PKG} packages ..."
listing="$(tar tzf "$BUNDLE")"
missing=""
for want in wazuh-manager wazuh-indexer wazuh-dashboard filebeat; do
  if ! printf '%s\n' "$listing" | grep -Eq "wazuh-packages/.*${want}.*\.${PKG}\$"; then
    missing="${missing} ${want}"
  fi
done
if [ -n "$missing" ]; then
  echo "  Bundle contents (wazuh-packages/*):"
  printf '%s\n' "$listing" | grep -E "wazuh-packages/.*\.(deb|rpm)$" | sed 's/^/    /' || true
  fail "Bundle is INCOMPLETE — missing:${missing}. Do NOT ship it. Rebuild on a matching ${PKG} host."
fi
ok "Bundle verified — wazuh-manager, wazuh-indexer, wazuh-dashboard and filebeat (${PKG}) all present."

# ── 5. Place it with the OS-specific name the platform prefers ───────────────
mkdir -p "$OUT_DIR"
cp "$BUNDLE" "$OUT_DIR/wazuh-offline-${PKG}.tar.gz"
cp wazuh-install.sh "$OUT_DIR/wazuh-install.sh"
size="$(du -h "$OUT_DIR/wazuh-offline-${PKG}.tar.gz" | cut -f1)"
ok "Wrote $OUT_DIR/wazuh-offline-${PKG}.tar.gz (${size}) and wazuh-install.sh"

cat <<EOF

──────────────────────────────────────────────────────────────────────────────
 Airgap bundle ready. Copy BOTH files into the platform's packages dir:

   scp $OUT_DIR/wazuh-offline-${PKG}.tar.gz \\
       $OUT_DIR/wazuh-install.sh \\
       user@platform:/opt/sabc-compliance/backend/packages/wazuh-manager/

 Certificates are handled automatically: leave them out and the platform
 generates them on the target during the offline install (all-in-one, 127.0.0.1)
 — you do NOT need to hand-edit config.yml. If you prefer to pre-generate certs,
 also drop a wazuh-install-files.tar in the same dir.

 Then run the Wazuh manager install from the platform. The playbook detects
 wazuh-offline-${PKG}.tar.gz and installs fully offline.
──────────────────────────────────────────────────────────────────────────────
EOF
