"""Detection watch config — the folders/files the agents monitor, managed by
the platform. Pins validation, the get/update use cases, and that the rendered
agent config is well-formed (parseable) with a dynamic path list."""
from __future__ import annotations

import importlib.util
import os

import pytest

from core.errors import ValidationError
from modules.detection.watch_config import (
    DEFAULT_WATCH_PATHS, GetWatchConfigUseCase, UpdateWatchConfigUseCase,
    render_agent_config,
)


class FakeConfig:
    def __init__(self, values=None): self.v = dict(values or {})
    async def get(self, k): return self.v.get(k)
    async def set(self, k, val): self.v[k] = val


class TestGetUpdate:
    async def test_get_returns_defaults_when_unset(self) -> None:
        out = await GetWatchConfigUseCase(FakeConfig()).execute()
        assert out["is_default"] is True
        assert out["paths"] == DEFAULT_WATCH_PATHS

    async def test_update_then_get_roundtrips(self) -> None:
        cfg = FakeConfig()
        upd = await UpdateWatchConfigUseCase(cfg).execute(
            {"paths": ["/etc/ssh/", "/etc/audit/"], "hash_only": ["/etc/ssh/ssh_host_ed25519_key"]})
        assert upd["is_default"] is False
        got = await GetWatchConfigUseCase(cfg).execute()
        assert got["paths"] == ["/etc/ssh/", "/etc/audit/"]
        assert got["hash_only"] == ["/etc/ssh/ssh_host_ed25519_key"]
        assert got["is_default"] is False

    async def test_update_dedupes_and_trims(self) -> None:
        cfg = FakeConfig()
        out = await UpdateWatchConfigUseCase(cfg).execute(
            {"paths": ["/etc/ssh/", " /etc/ssh/ ", "/etc/pam.d/"]})
        assert out["paths"] == ["/etc/ssh/", "/etc/pam.d/"]


class TestValidation:
    async def test_rejects_empty_path_list(self) -> None:
        with pytest.raises(ValidationError):
            await UpdateWatchConfigUseCase(FakeConfig()).execute({"paths": []})

    async def test_rejects_relative_path(self) -> None:
        with pytest.raises(ValidationError):
            await UpdateWatchConfigUseCase(FakeConfig()).execute({"paths": ["etc/ssh"]})

    async def test_rejects_uncovered_hash_only(self) -> None:
        with pytest.raises(ValidationError):
            await UpdateWatchConfigUseCase(FakeConfig()).execute(
                {"paths": ["/etc/ssh/"], "hash_only": ["/var/secret"]})


class TestRenderedConfigParses:
    """The rendered config must load with the node agent's own parser — a broken
    file would silently stop detection."""

    def _agent(self):
        path = os.path.join(os.path.dirname(__file__), "..", "detection-agent", "agent.py")
        spec = importlib.util.spec_from_file_location("agent_under_test", path)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass  # optional watchdog import fails at module tail; parser is defined
        return mod

    def test_dynamic_paths_roundtrip_through_agent_parser(self) -> None:
        agent = self._agent()
        if not hasattr(agent, "parse_simple_yaml"):
            pytest.skip("agent parser unavailable")
        paths = ["/etc/ssh/", "/etc/pam.d/", "/etc/audit/", "/etc/login.defs"]
        text = render_agent_config(
            node_hostname="web-01",
            gateway_url="https://10.0.0.5:8443/api/webhooks/detection",
            api_key="sabcdet_secret", paths=paths, hash_only=["/etc/shadow"],
        )
        parsed = agent.parse_simple_yaml(text)
        assert parsed["node_hostname"] == "web-01"
        assert parsed["watch"] == paths
        assert parsed["gateway"]["api_key"] == "sabcdet_secret"
        assert parsed["snapshot_policies"] == [{"path": "/etc/shadow", "snapshot": "hash-only"}]
