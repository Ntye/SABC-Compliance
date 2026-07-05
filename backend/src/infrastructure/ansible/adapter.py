from __future__ import annotations
import asyncio
import json
import logging
import os
import tempfile
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


STUB_STEPS: dict[str, list[str]] = {
    "install_puppet_master.yml": [
        "Gather facts",
        "Check for offline puppet packages (airgap detection)",
        "Install Java 17 (required by puppetserver)",
        "Install puppetserver package",
        "Configure JVM heap size",
        "Configure /etc/puppetlabs/puppet/puppet.conf",
        "Open firewall port 8140",
        "Enable and start puppetserver",
        "Wait for port 8140 to open",
        "Verify Puppet Server is running",
    ],
    "install_puppet_agent.yml": [
        "Gather facts",
        "Preflight — sync clock (chrony) to avoid 'cert not yet valid'",
        "Preflight — verify Puppet master port 8140 is reachable",
        "Check for offline puppet-agent packages (airgap detection)",
        "Install puppet-agent package",
        "Configure puppet.conf (server = puppet_master_host)",
        "Submit CSR and sign certificate on master",
        "Run first catalog (self-heals stale certs from VM clones)",
    ],
    "install_detection_agent.yml": [
        "Gather facts",
        "Install python3 + watchdog (distro package or pip)",
        "Copy the compliance detection agent",
        "Write /etc/compliance-agent/config.yaml",
        "Install systemd unit",
        "Enable and start compliance-detection-agent",
        "Verify the agent is running",
    ],
    "provision.yml": [
        "Gather facts",
        "Update package cache",
        "Install baseline packages (curl git vim net-tools chrony rsyslog)",
        "Enable and start chrony (NTP synchronisation)",
        "Enable and start rsyslog",
        "SSH hardening (PermitRootLogin, PasswordAuthentication, MaxAuthTries)",
        "Apply kernel security parameters (sysctl)",
    ],
}


class AnsibleAdapter:
    def __init__(self, ansible_dir: str, ssh_key_path: str, packages_dir: str = "") -> None:
        self._ansible_dir = os.path.abspath(ansible_dir)
        self._ssh_key_path = os.path.abspath(ssh_key_path)
        self._packages_dir = os.path.abspath(packages_dir) if packages_dir else ""
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
        vars_path = await self._write_vars(extra_vars)

        cmd = [
            "ansible-playbook",
            "-i", inv_path,
            playbook_path,
            "--extra-vars", f"@{vars_path}",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self._ansible_dir,
                limit=1024 * 1024,   # 1 MiB StreamReader buffer (not relied upon)
            )
            self._running[job_id] = proc

            # Read fixed-size chunks and split on newlines ourselves. The default
            # line iterator (`async for line in proc.stdout`) raises asyncio's
            # LimitOverrunError — "Separator is not found, and chunk exceed the
            # limit" — as soon as a single line exceeds the 64 KiB buffer. The
            # Puppet Enterprise installer runs via async and returns its ENTIRE
            # install log as one JSON line, which easily blows past that limit and
            # would crash this reader (masking the real installer error). Chunked
            # read() has no per-line limit.
            buf = b""
            FLUSH = 256 * 1024   # emit an unterminated line once it grows this big
            while True:
                chunk = await proc.stdout.read(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    line = raw.decode(errors="replace").rstrip("\r")
                    if line:
                        await on_line(line)
                if len(buf) >= FLUSH:
                    await on_line(buf.decode(errors="replace"))
                    buf = b""
            if buf:
                line = buf.decode(errors="replace").rstrip("\r")
                if line:
                    await on_line(line)

            await proc.wait()
            return proc.returncode or 0
        finally:
            self._running.pop(job_id, None)
            for path in (inv_path, vars_path):
                try:
                    os.unlink(path)
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
        raw_key = node.ssh_key_path or self._ssh_key_path
        key = os.path.abspath(raw_key)
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

    async def _write_vars(self, extra_vars: dict) -> str:
        merged = dict(extra_vars)
        if self._packages_dir:
            merged.setdefault("packages_dir", self._packages_dir)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(merged, f)
            return f.name

    async def _simulate(self, playbook: str, node, on_line) -> int:
        target = node.hostname if node else "localhost"
        steps = STUB_STEPS.get(playbook, [f"Execute {playbook}"])

        await on_line(f"PLAY [Install on {target}] {'*' * 46}\n")
        for step in steps:
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
