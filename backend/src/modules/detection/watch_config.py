"""
Detection watch configuration — which folders and files the detection agents
monitor, managed centrally by the platform instead of hard-coded per install.

Stored in ``platform_config`` under ``detection_watch_config`` as JSON:

    {"paths": ["/etc/ssh/", ...], "hash_only": ["/etc/shadow"]}

``paths`` are the watched folders/files; ``hash_only`` are the sensitive ones
for which the agent records only a hash (never the contents), so the evidence
trail never itself copies a secret. The stored config is injected into every
agent install and can be re-applied to already-enrolled nodes.
"""
from __future__ import annotations

import json
import logging

from core.errors import ValidationError

logger = logging.getLogger(__name__)

WATCH_CONFIG_KEY = "detection_watch_config"

# The built-in default set — the security-relevant configuration surface. Kept
# in sync with the agent's own DEFAULT_WATCH_PATHS so a node with no override
# behaves identically whether or not the platform has stored a config.
DEFAULT_WATCH_PATHS: list[str] = [
    "/etc/ssh/",
    "/etc/pam.d/",
    "/etc/sudoers",
    "/etc/sudoers.d/",
    "/etc/passwd",
    "/etc/group",
    "/etc/shadow",
]
DEFAULT_HASH_ONLY_PATHS: list[str] = ["/etc/shadow"]


def _clean_paths(raw, *, field: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError(f"{field} must be a list of paths")
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        p = str(item).strip()
        if not p:
            continue
        if not p.startswith("/"):
            raise ValidationError(f"{field}: '{p}' must be an absolute path (start with '/')")
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def default_config() -> dict:
    return {"paths": list(DEFAULT_WATCH_PATHS), "hash_only": list(DEFAULT_HASH_ONLY_PATHS)}


def render_agent_config(
    *, node_hostname: str, gateway_url: str, api_key: str,
    paths: list[str], hash_only: list[str],
    debounce_seconds: int = 2, heartbeat_interval_seconds: int = 600,
) -> str:
    """Render the agent's /etc/compliance-agent/config.yaml deterministically.

    Rendered in Python (not templated in the playbook) so the watched-path list
    is dynamic without risking block-scalar/Jinja indentation corrupting the
    file — a broken config would silently stop detection. Matches the minimal
    YAML subset the agent parses.
    """
    watch = paths or list(DEFAULT_WATCH_PATHS)
    lines = [
        "# Managed by the SABC compliance platform (detection watch config).",
        f"node_hostname: {node_hostname}",
        "",
        "gateway:",
        f"  url: {gateway_url}",
        f"  api_key: {api_key}",
        "  verify_tls: false",
        "",
        "watch:",
        *[f"  - {p}" for p in watch],
        "",
        "snapshot_policies:",
    ]
    for p in (hash_only or []):
        lines += [f"  - path: {p}", "    snapshot: hash-only"]
    lines += [
        "",
        f"debounce_seconds: {debounce_seconds}",
        f"heartbeat_interval_seconds: {heartbeat_interval_seconds}",
        "spool_dir: /var/spool/compliance-agent",
        "state_dir: /var/lib/compliance-agent",
        "",
    ]
    return "\n".join(lines)


class GetWatchConfigUseCase:
    def __init__(self, config_repo) -> None:
        self._cfg = config_repo

    async def execute(self) -> dict:
        raw = await self._cfg.get(WATCH_CONFIG_KEY)
        if not raw:
            return {**default_config(), "is_default": True}
        try:
            data = json.loads(raw)
            return {
                "paths": data.get("paths") or list(DEFAULT_WATCH_PATHS),
                "hash_only": data.get("hash_only") or [],
                "is_default": False,
            }
        except (ValueError, TypeError):
            logger.warning("Stored watch config is corrupt; serving defaults")
            return {**default_config(), "is_default": True}


class UpdateWatchConfigUseCase:
    def __init__(self, config_repo) -> None:
        self._cfg = config_repo

    async def execute(self, data: dict, actor: str | None = None) -> dict:
        paths = _clean_paths(data.get("paths"), field="paths")
        if not paths:
            raise ValidationError("At least one path must be monitored.")
        hash_only = _clean_paths(data.get("hash_only"), field="hash_only")
        # hash_only entries only make sense if they're covered by a watched path.
        for h in hash_only:
            if not any(h == p or h.startswith(p) or p.startswith(h) for p in paths):
                raise ValidationError(
                    f"hash-only path '{h}' is not covered by any monitored path")
        payload = {"paths": paths, "hash_only": hash_only}
        await self._cfg.set(WATCH_CONFIG_KEY, json.dumps(payload))
        logger.info("AUDIT detection-watch-config update by=%s paths=%d hash_only=%d",
                    actor or "unknown", len(paths), len(hash_only))
        return {**payload, "is_default": False}


class ApplyWatchConfigUseCase:
    """Push the current watch config to already-enrolled nodes by re-running the
    (idempotent) detection-agent install, which rewrites the agent config and
    restarts it. Returns the launched job per node."""

    def __init__(self, node_repo, install_detection_agent_uc) -> None:
        self._nodes = node_repo
        self._install = install_detection_agent_uc

    async def execute(self, node_id: str | None = None, actor: str | None = None) -> dict:
        if node_id:
            node = await self._nodes.find_by_id(node_id)
            targets = [node] if node else []
        else:
            targets = [n for n in await self._nodes.find_all({})
                       if getattr(n, "detection_enrolled", False)]

        jobs: list[dict] = []
        for node in targets:
            try:
                job = await self._install.execute(node.id)
                jobs.append({"node_id": node.id, "hostname": node.hostname,
                             "job_id": job.id, "status": "launched"})
            except Exception as exc:
                jobs.append({"node_id": node.id, "hostname": node.hostname,
                             "status": "failed", "error": str(exc)})
        logger.info("AUDIT detection-watch-config apply by=%s launched=%d",
                    actor or "unknown", sum(1 for j in jobs if j["status"] == "launched"))
        return {"launched": sum(1 for j in jobs if j["status"] == "launched"),
                "requested": len(targets), "jobs": jobs}
