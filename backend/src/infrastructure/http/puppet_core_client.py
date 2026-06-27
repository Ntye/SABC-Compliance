"""Puppet Core (open-source) node classifier via an External Node Classifier.

This is the no-cost production counterpart to ``PuppetNCClient`` (which drives
the PE-only RBAC + Node Classifier HTTP APIs). Puppet Core has neither API, so
classification is file-based: the platform deploys an ENC script + per-node
YAML to the master over SSH and points puppet.conf at it.

Two responsibilities, deliberately split by cost:

* ``configure_master`` — one-time, privileged: install the ENC script, set
  ``node_terminus = exec`` / ``external_nodes`` in puppet.conf and restart
  puppetserver. Done through the ``configure_puppet_core_enc`` Ansible playbook.
* ``apply_classification`` — every sync, cheap: rewrite the per-node YAML data
  files. An exec ENC is invoked fresh on each catalog request, so updating the
  data needs **no** puppetserver restart.

The client never calls any HTTP API that Puppet Core lacks.
"""
from __future__ import annotations
import base64
import logging

from core.errors import ExternalServiceError
from modules.node_groups import puppet_core_enc as enc

logger = logging.getLogger(__name__)


class PuppetCoreClient:
    def __init__(
        self,
        ssh_client,
        host: str | None = None,
        ssh_user: str = "root",
        ssh_key_path: str = "",
        enc_dir: str = "/etc/puppetlabs/puppet/enc",
        default_environment: str = "production",
        config_repo=None,
    ):
        self._ssh = ssh_client
        self._host = host
        self._env_host = host
        self._user = ssh_user
        self._key = ssh_key_path
        self._enc_dir = enc_dir.rstrip("/")
        self._default_env = default_environment
        self._config = config_repo

    async def _resolve(self) -> None:
        """Refresh master host from the platform-config DB (set when the master
        is installed through the console), falling back to the env value."""
        if not self._config:
            return
        try:
            host = await self._config.get("puppet_master_host")
        except Exception:
            return
        self._host = host or self._env_host

    async def is_configured(self) -> bool:
        await self._resolve()
        return bool(self._host)

    def _run(self, command: str):
        # ISSHClient.run_command(ip, port, user, key_path, command) -> (out, err, rc)
        return self._ssh.run_command(self._host, 22, self._user, self._key, command)

    async def apply_classification(self, classifications: list[dict]) -> dict:
        """Regenerate and push the per-node ENC data to the master.

        Writes ``<enc_dir>/nodes/<certname>.yaml`` for every managed node and
        refreshes the ``classify`` script + ``default.yaml``. Stale node files
        are cleared first so removed nodes stop being classified. Returns a
        small summary; raises ExternalServiceError on SSH failure.
        """
        await self._resolve()
        if not self._host:
            return {"deployed": 0, "skipped": True}

        artifacts = enc.build_enc_artifacts(
            classifications, self._enc_dir, self._default_env
        )
        script = self._render_deploy_script(artifacts)
        try:
            out, err, rc = await self._run(script)
        except Exception as e:
            raise ExternalServiceError(f"Puppet Core ENC deploy failed: {e}") from e
        if rc != 0:
            raise ExternalServiceError(
                f"Puppet Core ENC deploy returned {rc}: {err or out}"
            )
        node_files = sum(1 for p in artifacts if p.startswith("nodes/"))
        return {"deployed": node_files, "skipped": False}

    def _render_deploy_script(self, artifacts: dict[str, str]) -> str:
        """Build one idempotent remote shell script that writes every artifact.

        Each file's content is base64-encoded so arbitrary YAML (quotes,
        newlines, unicode) survives the single SSH command unharmed.
        """
        d = self._enc_dir
        lines = [
            "set -e",
            f"mkdir -p '{d}/nodes'",
            # Clear stale per-node files so de-classified nodes drop out.
            f"rm -f '{d}/nodes/'*.yaml 2>/dev/null || true",
        ]
        for relpath, content in artifacts.items():
            b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
            target = f"{d}/{relpath}"
            lines.append(f"printf '%s' '{b64}' | base64 -d > '{target}'")
        lines.append(f"chmod 0755 '{d}/classify'")
        # Ownership: puppetserver runs as the 'puppet' user; the ENC must be
        # readable by it. Best-effort — ignore if the user doesn't exist.
        lines.append(
            f"chown -R puppet:puppet '{d}' 2>/dev/null || true"
        )
        return "\n".join(lines) + "\n"

    async def health(self) -> dict:
        await self._resolve()
        if not self._host:
            return {"status": "not_configured"}
        try:
            out, err, rc = await self._run(
                f"test -x '{self._enc_dir}/classify' && echo ok || echo missing"
            )
            if rc == 0 and "ok" in (out or ""):
                return {"status": "up", "edition": "core", "enc_dir": self._enc_dir}
            return {"status": "degraded", "edition": "core",
                    "detail": "ENC script not installed; run configure"}
        except Exception:
            return {"status": "error", "edition": "core"}
