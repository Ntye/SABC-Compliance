from __future__ import annotations
import asyncio
import logging

from core.domain.interfaces import ISSHClient

logger = logging.getLogger(__name__)


class SshClientAdapter(ISSHClient):
    def __init__(self, default_key_path: str) -> None:
        self._default_key = default_key_path

    def _base_args(self, ip: str, port: int, user: str, key_path: str | None) -> list[str]:
        key = key_path or self._default_key
        return [
            "-i", key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=5",
            "-o", "BatchMode=yes",
            "-p", str(port),
            f"{user}@{ip}",
        ]

    async def test_connectivity(self, ip: str, port: int, user: str, key_path: str | None) -> tuple[bool, str | None]:
        args = self._base_args(ip, port, user, key_path)
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "ssh", *args, "echo OK",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=8,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=8)
            if proc.returncode == 0 and b"OK" in stdout:
                return True, None
            err = stderr.decode(errors="replace").strip() or f"SSH exited with code {proc.returncode}"
            return False, err
        except asyncio.TimeoutError:
            return False, "SSH connection timed out after 8s"
        except Exception as exc:
            return False, str(exc)

    async def run_command(self, ip: str, port: int, user: str, key_path: str | None, command: str) -> tuple[str, str, int]:
        args = self._base_args(ip, port, user, key_path)
        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "ssh", *args, command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=15,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            return (
                stdout.decode(errors="replace"),
                stderr.decode(errors="replace"),
                proc.returncode or 0,
            )
        except asyncio.TimeoutError:
            return "", "Command timed out after 15s", 1
        except Exception as exc:
            return "", str(exc), 1
