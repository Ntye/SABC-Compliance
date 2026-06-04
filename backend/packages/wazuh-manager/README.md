# Wazuh Manager — Offline Packages

Place offline installation files here before building the airgap image or running the Ansible playbook.

## Docker-based install (recommended)

Export the three Wazuh images on any machine that has them:

```bash
docker save \
  wazuh/wazuh-manager:4.10.4 \
  wazuh/wazuh-indexer:4.10.4 \
  wazuh/wazuh-dashboard:4.10.4 \
  --output backend/packages/wazuh-manager/wazuh-docker-images-4.10.4.tar
```

The Ansible playbook `install_wazuh_manager_docker.yml` transfers this tarball
to the target node, loads the images, and starts the stack with Docker Compose.

## Script-based install (alternative)

For bare-metal / no-Docker targets, use `wazuh-install.sh` + `wazuh-offline.tar.gz`
and the `install_wazuh_manager.yml` playbook instead.
