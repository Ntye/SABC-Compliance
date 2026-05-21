from __future__ import annotations
import asyncio
import logging
import os
import tempfile
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


STUB_STEPS: dict[str, list[str]] = {
    "install_puppet_master.yml": [
        "Verify system requirements",
        "Add Puppet Platform repository",
        "Install puppetserver package",
        "Configure /etc/puppetlabs/puppet/puppet.conf",
        "Enable and start puppetserver service",
        "Open firewall ports 8140 and 8143",
        "Generate Puppet CA certificate",
        "Verify Puppet API is reachable",
    ],
    "install_wazuh_manager.yml": [
        "Verify system requirements",
        "Add Wazuh repository",
        "Install wazuh-manager package",
        "Install filebeat package",
        "Configure wazuh-manager (ossec.conf)",
        "Enable and start wazuh-manager service",
        "Open firewall ports 1514 1515 55000",
        "Verify Wazuh API is reachable",
    ],
    "install_puppet_agent.yml": [
        "Verify system requirements",
        "Add Puppet Platform repository",
        "Install puppet-agent package",
        "Configure puppet.conf (server = puppet_master)",
        "Enable and start puppet service",
        "Submit certificate signing request to Puppet master",
        "Run initial Puppet catalog apply",
    ],
    "install_wazuh_agent.yml": [
        "Verify system requirements",
        "Add Wazuh repository",
        "Install wazuh-agent package",
        "Configure ossec.conf (manager_address = wazuh_manager)",
        "Enable and start wazuh-agent service",
        "Register agent with Wazuh manager",
        "Verify agent active connection",
    ],
    "provision.yml": [
        "Gather facts",
        "Update package cache",
        "Install baseline packages (curl git vim)",
        "Configure NTP synchronisation",
        "Configure SSH hardening",
        "Configure system logging (rsyslog)",
        "Apply kernel security parameters (sysctl)",
    ],
}


class AnsibleAdapter:
    def __init__(self, ansible_dir: str, ssh_key_path: str) -> None:
        self._ansible_dir = os.path.abspath(ansible_dir)
        self._ssh_key_path = ssh_key_path
        self._running: dict[str, asyncio.subprocess.Process] = {}

    async def run_playbook(
        self,
        job_id: str,
        node,
        playbook: str,
        extra_vars: dict,
        on_line: Callable[[str], Awaitable[None]],
    ) -> int:
        playbook_path = os.path.join(self._ansible_dir, "playbooks", playbook)

        if not os.path.exists(playbook_path):
            await on_line(f"ERROR: Playbook not found: {playbook_path}")
            return 1

        ansible_available = await self._check_ansible()

        if not ansible_available:
            await on_line("(ansible-playbook not found — running in stub/simulation mode)")
            await on_line("")
            return await self._simulate(playbook, node, on_line)

        inv_path = await self._write_inventory(node)
        cmd = ["ansible-playbook", "-i", inv_path, playbook_path]
        if extra_vars:
            cmd += ["--extra-vars", " ".join(f"{k}={v}" for k, v in extra_vars.items())]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self._ansible_dir,
            )
            self._running[job_id] = proc

            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if line:
                    await on_line(line)

            await proc.wait()
            return proc.returncode or 0
        finally:
            self._running.pop(job_id, None)
            try:
                os.unlink(inv_path)
            except OSError:
                pass

    def cancel(self, job_id: str) -> None:
        proc = self._running.get(job_id)
        if proc and proc.returncode is None:
            proc.terminate()

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _check_ansible(self) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ansible-playbook", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def _write_inventory(self, node) -> str:
        key = node.ssh_key_path or self._ssh_key_path
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            if node:
                f.write(
                    "[target]\n"
                    f"{node.ip} "
                    f"ansible_user={node.ssh_user} "
                    f"ansible_ssh_private_key_file={key} "
                    f"ansible_ssh_common_args='-o StrictHostKeyChecking=no'\n"
                )
            else:
                f.write("[target]\nlocalhost ansible_connection=local\n")
            return f.name

    async def _simulate(self, playbook: str, node, on_line) -> int:
        target = node.hostname if node else "localhost"
        steps = STUB_STEPS.get(playbook, [f"Execute {playbook}"])

        await on_line(f"PLAY [Install on {target}] {'*' * 46}\n")
        for i, step in enumerate(steps, 1):
            pad = max(1, 62 - len(step))
            await on_line(f"TASK [{step}] {'*' * pad}")
            await asyncio.sleep(0.5)
            await on_line(f"ok: [{target}]\n")

        await on_line(f"PLAY RECAP {'*' * 60}")
        await on_line(
            f"{target:<30}: ok={len(steps):<3} changed=0  "
            "unreachable=0  failed=0  skipped=0"
        )
        return 0
