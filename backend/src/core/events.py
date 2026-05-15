from __future__ import annotations
import asyncio
import logging
from typing import Callable

from .domain.interfaces import IEventBus

logger = logging.getLogger(__name__)


NODE_REGISTERED = "node.registered"
JOB_STARTED = "job.started"
JOB_LOG_LINE = "job.log_line"
JOB_COMPLETED = "job.completed"
COMPLIANCE_VIOLATION_DETECTED = "compliance.violation_detected"
REMEDIATION_TRIGGERED = "remediation.triggered"
REMEDIATION_COMPLETED = "remediation.completed"


class EventBus(IEventBus):
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}

    def subscribe(self, event_name: str, handler: Callable) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def publish(self, event_name: str, payload: dict) -> None:
        for handler in self._handlers.get(event_name, []):
            async def _safe(h=handler, p=payload):
                try:
                    await h(p)
                except Exception as exc:
                    logger.error("Event handler error [%s]: %s", event_name, exc)
            asyncio.create_task(_safe())
