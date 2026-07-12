"""Scan-history use cases: fleet/node history rows + single-report fetch."""
from __future__ import annotations

from datetime import datetime

import pytest

from core.domain.entities import ComplianceReport, Node
from core.errors import NotFoundError
from modules.compliance.usecases import (
    GetComplianceHistoryUseCase, GetComplianceReportUseCase,
)


class FakeNodeRepo:
    def __init__(self, nodes): self.nodes = {n.id: n for n in nodes}
    async def find_by_id(self, i): return self.nodes.get(i)
    async def find_by_hostname(self, h): return next((n for n in self.nodes.values() if n.hostname == h), None)
    async def find_all(self, f): return list(self.nodes.values())


class FakeComplianceRepo:
    def __init__(self, history=None, reports=None):
        self._history = history or []
        self._reports = {r.id: r for r in (reports or [])}

    async def find_history(self, node_id=None, since=None, until=None, limit=1000):
        rows = [r for r in self._history
                if (not node_id or r["node_id"] == node_id)
                and (not since or r["collected_at"] >= since)
                and (not until or r["collected_at"] <= until)]
        return rows[:limit]

    async def find_report(self, report_id):
        return self._reports.get(report_id)


NODES = [Node(id="n1", hostname="web-01", ip="10.0.0.5"),
         Node(id="n2", hostname="db-01", ip="10.0.0.6")]


def _row(rid, node_id, at, score=90):
    return {"id": rid, "node_id": node_id, "score": score, "source": "scan",
            "collected_at": at, "passed_checks": score, "failed_checks": 100 - score,
            "total_checks": 100}


class TestHistory:
    async def test_fleet_history_tags_hostnames(self) -> None:
        repo = FakeComplianceRepo(history=[
            _row("r1", "n1", "2026-07-01T10:00:00"),
            _row("r2", "n2", "2026-07-02T10:00:00"),
        ])
        uc = GetComplianceHistoryUseCase(FakeNodeRepo(NODES), repo)
        out = await uc.execute()
        assert {r["hostname"] for r in out} == {"web-01", "db-01"}

    async def test_node_scoped_history_resolves_by_hostname(self) -> None:
        repo = FakeComplianceRepo(history=[
            _row("r1", "n1", "2026-07-01T10:00:00"),
            _row("r2", "n2", "2026-07-02T10:00:00"),
        ])
        uc = GetComplianceHistoryUseCase(FakeNodeRepo(NODES), repo)
        out = await uc.execute(node_id="web-01")   # hostname resolves to n1
        assert [r["id"] for r in out] == ["r1"]
        assert out[0]["hostname"] == "web-01"

    async def test_time_window_filters(self) -> None:
        repo = FakeComplianceRepo(history=[
            _row("r1", "n1", "2026-07-01T10:00:00"),
            _row("r2", "n1", "2026-07-05T10:00:00"),
            _row("r3", "n1", "2026-07-09T10:00:00"),
        ])
        uc = GetComplianceHistoryUseCase(FakeNodeRepo(NODES), repo)
        out = await uc.execute(since="2026-07-03T00:00:00", until="2026-07-06T00:00:00")
        assert [r["id"] for r in out] == ["r2"]


class TestReport:
    async def test_returns_details_and_hostname(self) -> None:
        rep = ComplianceReport(id="r1", node_id="n1", source="scan", framework="cis",
                               passed_checks=90, failed_checks=10, total_checks=100,
                               details=[{"control_id": "JR2.C.1", "status": "pass"}],
                               collected_at=datetime(2026, 7, 1, 10))
        uc = GetComplianceReportUseCase(FakeNodeRepo(NODES), FakeComplianceRepo(reports=[rep]))
        out = await uc.execute("r1")
        assert out["hostname"] == "web-01"
        assert out["score"] == 90
        assert out["details"][0]["control_id"] == "JR2.C.1"

    async def test_missing_report_raises(self) -> None:
        uc = GetComplianceReportUseCase(FakeNodeRepo(NODES), FakeComplianceRepo())
        with pytest.raises(NotFoundError):
            await uc.execute("ghost")
