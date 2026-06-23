from __future__ import annotations
import time
import httpx
from core.errors import ExternalServiceError


class WazuhRESTClient:
    def __init__(self, host, port, user, password, token_refresh_seconds=840):
        self._host = host
        self._port = port
        self._user = user
        self._pass = password
        self._refresh = token_refresh_seconds
        self._token = None
        self._token_ts = 0.0

    def _base(self):
        return f"https://{self._host}:{self._port}"

    async def _jwt(self) -> str:
        if self._token and (time.time() - self._token_ts) < self._refresh:
            return self._token
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.post(
                    f"{self._base()}/security/user/authenticate",
                    params={"raw": "true"},
                    auth=(self._user, self._pass or "wazuh"),
                    timeout=10,
                )
                r.raise_for_status()
                self._token = r.text.strip()
                self._token_ts = time.time()
                return self._token
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Wazuh auth failed: {e}") from e

    async def create_agent_group(self, name: str) -> None:
        if not self._host:
            return
        token = await self._jwt()
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.post(
                    f"{self._base()}/groups",
                    json={"group_id": name},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if r.status_code not in (200, 400):  # 400 = already exists
                    r.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Wazuh create group failed: {e}") from e

    async def delete_agent_group(self, name: str) -> None:
        if not self._host:
            return
        token = await self._jwt()
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.delete(
                    f"{self._base()}/groups",
                    params={"groups_list": name},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                if r.status_code not in (200, 404):
                    r.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Wazuh delete group failed: {e}") from e

    async def assign_agents_to_group(self, group_name: str, hostnames: list[str]) -> dict:
        """Assign the given agents (matched by name/hostname) to an agent group.

        Returns {"assigned": [...], "missing": [...]}. Best-effort: agents not
        found in Wazuh are reported as missing rather than raising.
        """
        result = {"assigned": [], "missing": list(hostnames)}
        if not self._host or not hostnames:
            return result
        agents = await self.list_agents()
        # Map by both name and a normalised short hostname
        by_name = {}
        for a in agents:
            nm = (a.get("name") or "").lower()
            if nm:
                by_name[nm] = a.get("id")
                by_name[nm.split(".")[0]] = a.get("id")
        token = await self._jwt()
        async with httpx.AsyncClient(verify=False) as c:
            for host in hostnames:
                key = (host or "").lower()
                agent_id = by_name.get(key) or by_name.get(key.split(".")[0])
                if not agent_id:
                    continue
                try:
                    r = await c.put(
                        f"{self._base()}/agents/{agent_id}/group/{group_name}",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    if r.status_code in (200, 201):
                        result["assigned"].append(host)
                        if host in result["missing"]:
                            result["missing"].remove(host)
                except httpx.HTTPError as e:
                    raise ExternalServiceError(f"Wazuh assign agent failed: {e}") from e
        return result

    async def list_agents(self) -> list[dict]:
        if not self._host:
            return []
        try:
            token = await self._jwt()
            async with httpx.AsyncClient(verify=False) as c:
                r = await c.get(
                    f"{self._base()}/agents",
                    params={"pretty": "true"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10,
                )
                r.raise_for_status()
                return r.json().get("data", {}).get("affected_items", [])
        except Exception:
            return []

    async def get_alerts(self, since: str, agent_name: str) -> list[dict]:
        return []

    async def get_sca_results(self, agent_id: str, policy_id: str) -> list[dict]:
        return []

    async def health(self) -> dict:
        if not self._host:
            return {"status": "not_configured"}
        try:
            token = await self._jwt()
            async with httpx.AsyncClient(verify=False) as c:
                r = await c.get(
                    f"{self._base()}/",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5,
                )
                return {"status": "up" if r.status_code == 200 else "degraded"}
        except Exception:
            return {"status": "error"}
