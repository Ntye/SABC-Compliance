from __future__ import annotations
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

UNITS_TO_SECONDS: dict[str, int] = {"seconds": 1, "minutes": 60, "days": 86400}

# How often the scheduler wakes to re-check config and due-time.
# 30 s means config changes take effect within half a minute.
_POLL = 30


class AutoScanScheduler:
    """Periodically runs compliance scans across the whole fleet.

    Schedule is stored in ``platform_config`` so changes survive restarts and
    take effect within ``_POLL`` seconds without restarting the platform.

    Keys used:
        auto_scan_enabled   "true" | "false"  (default "true")
        auto_scan_interval  positive integer   (default 30)
        auto_scan_unit      "seconds" | "minutes" | "days"  (default "minutes")
        auto_scan_last_run  ISO-8601 UTC timestamp of the last completed run
    """

    def __init__(self, collect_uc, node_repo, config_repo) -> None:
        self._collect_uc = collect_uc
        self._nodes = node_repo
        self._cfg = config_repo
        self._task: asyncio.Task | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._task = asyncio.get_event_loop().create_task(self._loop(), name="auto-scan-scheduler")
        logger.info("Auto-scan scheduler started (poll every %ds)", _POLL)

    def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Auto-scan scheduler stopped")

    # ── Internal loop ──────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_POLL)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Auto-scan scheduler error: %s", exc)

    async def _tick(self) -> None:
        enabled = (await self._cfg.get("auto_scan_enabled")) or "true"
        if enabled != "true":
            return

        interval = int((await self._cfg.get("auto_scan_interval")) or "30")
        unit = (await self._cfg.get("auto_scan_unit")) or "minutes"
        sleep_secs = interval * UNITS_TO_SECONDS.get(unit, 60)

        last_iso = await self._cfg.get("auto_scan_last_run")
        now = datetime.utcnow()
        if last_iso:
            elapsed = (now - datetime.fromisoformat(last_iso)).total_seconds()
            if elapsed < sleep_secs:
                return  # not due yet

        logger.info("Auto-scan: starting scheduled fleet scan (interval=%d %s)", interval, unit)
        await self._cfg.set("auto_scan_last_run", now.isoformat())
        nodes = await self._nodes.find_all({})
        ok = failed = 0
        for node in nodes:
            try:
                await self._collect_uc.execute(node.id)
                ok += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Auto-scan: node %s failed: %s",
                    getattr(node, "hostname", node.id),
                    exc,
                )
        logger.info("Auto-scan complete: %d succeeded, %d failed", ok, failed)
