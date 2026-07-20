"""Detection Events listing: events from nodes removed from the registry are
kept in the DB as evidence but dropped from the operator view — they would
show a raw node UUID and inflate the active-alerts count with alerts nobody
can act on or resolve.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.entities import ConfigChangeEvent, Node
from modules.detection.usecases import ListDetectionEventsUseCase


def _event(node_id: str) -> ConfigChangeEvent:
    return ConfigChangeEvent(
        id=f"e-{node_id}", node_id=node_id, path="/etc/passwd",
        event_type="modified", timestamp=datetime(2026, 7, 19, 8, 0, 0),
    )


class FakeNodeRepo:
    def __init__(self, nodes):
        self.nodes = nodes

    async def find_all(self, filters):
        return list(self.nodes)


class FakeDetectionRepo:
    def __init__(self, events):
        self.events = events

    async def find_events(self, node_id=None, limit=100, include_heartbeats=False):
        return list(self.events)


@pytest.mark.asyncio
async def test_events_from_deleted_nodes_are_hidden() -> None:
    live = Node(id="live-node", hostname="web-01", ip="10.0.0.1")
    events = [_event("live-node"), _event("deleted-node")]
    uc = ListDetectionEventsUseCase(FakeDetectionRepo(events), FakeNodeRepo([live]))

    out = await uc.execute()

    assert [e["node_id"] for e in out] == ["live-node"]
    assert out[0]["hostname"] == "web-01"
