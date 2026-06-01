#!/bin/bash
set -e

# ── Seed packages volume from bundled files (airgap build) ───────────────────
# When the image is built with Dockerfile.bundle, pre-downloaded packages are
# stored at /app/bundled/.  On the first start against a fresh volume we copy
# them into the writable /app/packages/ directory so Ansible can find them.
if [ -d /app/bundled ] && [ "$(ls -A /app/bundled 2>/dev/null)" ]; then
    for pkg_dir in /app/bundled/*/; do
        pkg_name="$(basename "$pkg_dir")"
        dst="/app/packages/${pkg_name}"
        mkdir -p "$dst"
        # Only seed when the destination is empty (don't overwrite user files)
        if [ -z "$(ls -A "$dst" 2>/dev/null)" ]; then
            echo "[entrypoint] Seeding /app/packages/${pkg_name} from bundled ..."
            cp -r "${pkg_dir}." "$dst/"
        fi
    done
fi

# ── Generate Ansible SSH key pair on first start ──────────────────────────────
if [ ! -f /app/keys/ansible_id_rsa ]; then
    echo "[entrypoint] Generating SSH key pair at /app/keys/ansible_id_rsa ..."
    ssh-keygen -t rsa -b 4096 -f /app/keys/ansible_id_rsa -N "" -C "bdc-ansible"
    echo "[entrypoint] Done. Copy the public key to your managed nodes:"
    echo ""
    cat /app/keys/ansible_id_rsa.pub
    echo ""
fi

exec "$@"
