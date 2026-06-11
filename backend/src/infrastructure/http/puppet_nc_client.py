from __future__ import annotations
import time
import uuid
import httpx
from core.errors import ExternalServiceError


class PuppetNCClient:
    ROOT_GROUP = "00000000-0000-4000-8000-000000000000"

    def __init__(self, host, rbac_port=4433, admin_user="admin", admin_pass=None, token_rotate_seconds=43200):
        self._host = host
        self._port = rbac_port
        self._user = admin_user
        self._pass = admin_pass
        self._rotate = token_rotate_seconds
        self._token = None
        self._token_ts = 0.0

    def _rbac(self):
        return f"https://{self._host}:{self._port}"

    async def _token_hdr(self) -> dict:
        if self._token and (time.time() - self._token_ts) < self._rotate:
            return {"X-Authentication": self._token}
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.post(
                    f"{self._rbac()}/rbac-api/v1/auth/token",
                    json={"login": self._user, "password": self._pass or "", "lifetime": "1d"},
                    timeout=10,
                )
                r.raise_for_status()
                self._token = r.json()["token"]
                self._token_ts = time.time()
                return {"X-Authentication": self._token}
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Puppet RBAC auth failed: {e}") from e

    async def create_node_group(self, name: str, description: str | None = None) -> str:
        if not self._host:
            return ""
        hdrs = await self._token_hdr()
        group_id = str(uuid.uuid4())
        payload = {
            "id": group_id,
            "name": name,
            "environment": "production",
            "parent": self.ROOT_GROUP,
            "classes": {},
            "rule": None,
        }
        if description:
            payload["description"] = description
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.post(
                    f"{self._rbac()}/classifier-api/v1/groups",
                    json=payload,
                    headers={**hdrs, "Content-Type": "application/json"},
                    timeout=10,
                )
                if r.status_code not in (200, 201, 303):
                    r.raise_for_status()
                return group_id
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Puppet create node group failed: {e}") from e

    async def delete_node_group(self, puppet_group_id: str) -> None:
        if not self._host or not puppet_group_id:
            return
        hdrs = await self._token_hdr()
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.delete(
                    f"{self._rbac()}/classifier-api/v1/groups/{puppet_group_id}",
                    headers=hdrs,
                    timeout=10,
                )
                if r.status_code not in (204, 404):
                    r.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Puppet delete node group failed: {e}") from e

    async def trigger_run(self, node_fqdn: str, description: str) -> dict:
        return {"job_id": ""}

    async def get_job_result(self, job_id: str) -> dict:
        return {}

    async def list_nodes(self) -> list[dict]:
        return []

    async def get_node_report(self, node_fqdn: str) -> dict:
        return {}

    async def health(self) -> dict:
        if not self._host:
            return {"status": "not_configured"}
        try:
            hdrs = await self._token_hdr()
            async with httpx.AsyncClient(verify=False) as c:
                r = await c.get(
                    f"{self._rbac()}/status/v1/services",
                    headers=hdrs,
                    timeout=5,
                )
                return {"status": "up" if r.status_code == 200 else "degraded"}
        except Exception:
            return {"status": "error"}
