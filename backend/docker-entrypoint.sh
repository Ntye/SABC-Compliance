#!/bin/bash
set -e

# Generate the Ansible SSH key pair on first start.
# The /app/keys volume persists it across container restarts.
if [ ! -f /app/keys/ansible_id_rsa ]; then
    echo "[entrypoint] Generating SSH key pair at /app/keys/ansible_id_rsa ..."
    ssh-keygen -t rsa -b 4096 -f /app/keys/ansible_id_rsa -N "" -C "bdc-ansible"
    echo "[entrypoint] Done. Copy the public key to your managed nodes:"
    echo ""
    cat /app/keys/ansible_id_rsa.pub
    echo ""
fi

exec "$@"
