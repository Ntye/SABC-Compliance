"""
SSH key rotation — the platform's Ansible key changed over time, safely.

The private key at ``ssh_key_path`` is the master credential: its public half
sits in every managed node's ``authorized_keys`` and the matching user has
passwordless sudo. Rotating it periodically limits the value of a leaked key.

The rotation is **add-before-remove**, so a node always keeps at least one
working key and the platform can never lock itself out:

    1. generate a fresh keypair (.pending)
    2. for every node, APPEND the new public key using the CURRENT key, then
       VERIFY a login with the NEW key (explicit key → the previous-key
       fallback is not offered, so the test is truthful)
    3. if any REACHABLE node fails verification, ABORT and discard the pending
       key — nothing on disk changes, no node is disturbed
    4. otherwise PROMOTE (active → .prev, pending → active) atomically
    5. REMOVE the old public key from every node that verified, using the new
       key. Nodes unreachable in step 2 keep the old key and are reconciled on
       the next rotation (the adapter offers .prev as a fallback identity so
       they stay reachable in the meantime).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

ROTATE_ENABLED_KEY = "ssh_key_rotate_enabled"
ROTATE_DAYS_KEY = "ssh_key_rotate_days"
LAST_ROTATED_KEY = "ssh_key_last_rotated"
DEFAULT_ROTATE_DAYS = 90


def _authorized_keys_append_cmd(pub: str) -> str:
    return (
        "install -d -m 700 ~/.ssh && touch ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys && "
        f"(grep -qxF '{pub}' ~/.ssh/authorized_keys || printf '%s\\n' '{pub}' >> ~/.ssh/authorized_keys)"
    )


def _authorized_keys_remove_cmd(pub: str) -> str:
    return (
        f"grep -vxF '{pub}' ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.sabctmp 2>/dev/null; "
        "mv ~/.ssh/authorized_keys.sabctmp ~/.ssh/authorized_keys && "
        "chmod 600 ~/.ssh/authorized_keys"
    )


class RotateSshKeyUseCase:
    def __init__(self, node_repo, ssh_client, key_manager, config_repo=None,
                 event_bus=None) -> None:
        self._nodes = node_repo
        self._ssh = ssh_client
        self._km = key_manager
        self._cfg = config_repo
        self._bus = event_bus

    async def execute(self, actor: str | None = None, remove_old: bool = True) -> dict:
        old_pub = self._km.read_public_key()
        nodes = await self._nodes.find_all({})

        # A public key line must never contain a single quote (base64 + comment
        # never does); refuse rather than risk a broken remote shell command.
        new_pub = await self._km.generate_pending(
            comment=f"sabc-ansible-{datetime.utcnow().strftime('%Y%m%d')}"
        )
        if "'" in new_pub or (old_pub and "'" in old_pub):
            self._km.discard_pending()
            raise RuntimeError("refusing to rotate: a public key contains a single quote")

        # ── Phase 1: distribute the new key and verify it, per node ────────────
        entries: list[tuple[object, dict]] = []
        for node in nodes:
            r: dict = {"node_id": node.id, "hostname": node.hostname}
            add_ok, add_err = await self._append(node, new_pub, self._km.path)  # current key
            r["distributed"] = add_ok
            if not add_ok:
                r["status"] = "unreachable"
                r["error"] = add_err
            else:
                verified = await self._verify(node, self._km.pending_path)     # new key only
                r["verified"] = verified
                r["status"] = "ready" if verified else "verify_failed"
            entries.append((node, r))

        results = [r for _, r in entries]

        # ── Phase 2: safety gate ───────────────────────────────────────────────
        # A node we reached but whose new-key login failed would be at risk if we
        # promoted (it might end up trusting a key that doesn't work). Abort — the
        # active key on disk is untouched, so the fleet is exactly as before.
        verify_failures = [r for r in results if r.get("distributed") and not r.get("verified")]
        if verify_failures:
            self._km.discard_pending()
            self._publish("ssh_key.rotation_aborted", {"reason": "verify_failed"})
            return {
                "rotated": False,
                "reason": "New key could not be verified on one or more reachable nodes; "
                          "no change was made.",
                "nodes": results,
                **self._counts(results),
            }

        # ── Phase 3: promote (atomic) ──────────────────────────────────────────
        self._km.promote_pending()

        # ── Phase 4: remove the old key from the nodes that took the new one ────
        if remove_old and old_pub:
            for node, r in entries:
                if r.get("status") == "ready":
                    rm_ok, _ = await self._remove(node, old_pub, self._km.path)  # new key now
                    r["old_removed"] = rm_ok
                    r["status"] = "rotated" if rm_ok else "rotated_old_present"
        else:
            for r in results:
                if r.get("status") == "ready":
                    r["status"] = "rotated"

        now = datetime.utcnow()
        if self._cfg is not None:
            await self._cfg.set(LAST_ROTATED_KEY, now.isoformat())

        fp = await self._km.fingerprint()
        summary = {
            "rotated": True,
            "rotated_at": now.isoformat(),
            "fingerprint": fp,
            "nodes": results,
            **self._counts(results),
        }
        self._publish("ssh_key.rotated", {
            "fingerprint": (fp or {}).get("fingerprint"),
            "actor": actor, **self._counts(results),
        })
        logger.info("AUDIT ssh-key-rotate by=%s fingerprint=%s reachable=%d unreachable=%d",
                    actor or "unknown", (fp or {}).get("fingerprint"),
                    summary["reachable"], summary["unreachable"])
        return summary

    # ── Helpers ────────────────────────────────────────────────────────────────
    @staticmethod
    def _counts(results: list[dict]) -> dict:
        reachable = sum(1 for r in results if r.get("distributed"))
        return {
            "total": len(results),
            "reachable": reachable,
            "unreachable": len(results) - reachable,
            "old_key_retained": sum(1 for r in results if r.get("status") == "rotated_old_present"),
        }

    async def _append(self, node, pub: str, key_path: str) -> tuple[bool, str | None]:
        try:
            _, err, rc = await self._ssh.run_command(
                node.ip, node.ssh_port, node.ssh_user, key_path,
                _authorized_keys_append_cmd(pub),
            )
            return rc == 0, (err.strip() or None if rc != 0 else None)
        except Exception as exc:  # pragma: no cover - defensive
            return False, str(exc)

    async def _remove(self, node, pub: str, key_path: str) -> tuple[bool, str | None]:
        try:
            _, err, rc = await self._ssh.run_command(
                node.ip, node.ssh_port, node.ssh_user, key_path,
                _authorized_keys_remove_cmd(pub),
            )
            return rc == 0, (err.strip() or None if rc != 0 else None)
        except Exception as exc:  # pragma: no cover - defensive
            return False, str(exc)

    async def _verify(self, node, key_path: str) -> bool:
        try:
            ok, _ = await self._ssh.test_connectivity(
                node.ip, node.ssh_port, node.ssh_user, key_path,
            )
            return ok
        except Exception:  # pragma: no cover - defensive
            return False

    def _publish(self, name: str, payload: dict) -> None:
        if self._bus is not None:
            try:
                self._bus.publish(name, payload)
            except Exception as exc:
                logger.error("event publish failed [%s]: %s", name, exc)


class GetSshKeyStatusUseCase:
    def __init__(self, node_repo, key_manager, config_repo=None) -> None:
        self._nodes = node_repo
        self._km = key_manager
        self._cfg = config_repo

    async def execute(self) -> dict:
        fp = await self._km.fingerprint()
        try:
            nodes = await self._nodes.find_all({})
            node_count = len(nodes)
        except Exception:
            node_count = None

        enabled = False
        days = DEFAULT_ROTATE_DAYS
        last_iso = None
        if self._cfg is not None:
            enabled = (await self._cfg.get(ROTATE_ENABLED_KEY)) == "true"
            days = int((await self._cfg.get(ROTATE_DAYS_KEY)) or DEFAULT_ROTATE_DAYS)
            last_iso = await self._cfg.get(LAST_ROTATED_KEY)

        next_due = None
        if enabled and last_iso:
            try:
                next_due = (datetime.fromisoformat(last_iso) + timedelta(days=days)).isoformat()
            except ValueError:
                next_due = None

        return {
            "fingerprint": (fp or {}).get("fingerprint"),
            "type": (fp or {}).get("type"),
            "bits": (fp or {}).get("bits"),
            "has_previous": self._km.has_prev(),
            "node_count": node_count,
            "last_rotated": last_iso,
            "next_due": next_due,
            "schedule": {"enabled": enabled, "days": days},
        }


class SshKeyRotationScheduler:
    """Opt-in background rotation. Stored in ``platform_config`` so it survives
    restarts and takes effect within one poll without a restart. Disabled by
    default because rotation touches every managed node.

    Keys:
        ssh_key_rotate_enabled  "true" | "false"   (default "false")
        ssh_key_rotate_days     positive integer    (default 90)
        ssh_key_last_rotated    ISO-8601 UTC timestamp of the last rotation
    """

    _POLL = 3600  # re-check hourly; config changes apply within the hour

    def __init__(self, rotate_uc: RotateSshKeyUseCase, config_repo) -> None:
        self._rotate = rotate_uc
        self._cfg = config_repo
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(
            self._loop(), name="ssh-key-rotation-scheduler")
        logger.info("SSH key rotation scheduler started (poll every %ds)", self._POLL)

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("SSH key rotation scheduler stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._POLL)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # never let one failure kill the loop
                logger.error("SSH key rotation scheduler error: %s", exc)

    async def _tick(self) -> None:
        if (await self._cfg.get(ROTATE_ENABLED_KEY)) != "true":
            return
        days = int((await self._cfg.get(ROTATE_DAYS_KEY)) or DEFAULT_ROTATE_DAYS)
        last_iso = await self._cfg.get(LAST_ROTATED_KEY)
        now = datetime.utcnow()
        if last_iso:
            try:
                if (now - datetime.fromisoformat(last_iso)) < timedelta(days=days):
                    return  # not due yet
            except ValueError:
                pass
        logger.info("SSH key rotation: scheduled rotation is due (every %d days)", days)
        try:
            res = await self._rotate.execute(actor="scheduler")
            if not res.get("rotated"):
                logger.warning("Scheduled SSH key rotation did not complete: %s",
                               res.get("reason"))
        except Exception as exc:
            logger.error("Scheduled SSH key rotation failed: %s", exc)
