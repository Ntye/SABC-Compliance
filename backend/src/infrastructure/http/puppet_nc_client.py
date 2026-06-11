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

    # ── Rule translation ─────────────────────────────────────────────────────
    # Map our managed-node attributes to the closest Puppet fact reference.
    _FACT_MAP = {
        "os_family": ["facts", "osfamily"],
        "os_name": ["facts", "operatingsystem"],
        "os_version": ["facts", "operatingsystemrelease"],
        "ip": ["facts", "ipaddress"],
        "hostname": ["trusted", "certname"],
        "fqdn": ["trusted", "certname"],
    }

    def _fact_ref(self, fact: str):
        return self._FACT_MAP.get(fact, ["facts", fact])

    def _translate_rule(self, r: dict):
        """Translate one {fact, operator, value} into a PE rule condition."""
        op = (r.get("operator") or "=").strip()
        ref = self._fact_ref(r.get("fact", ""))
        val = r.get("value", "")
        if op == "!=":
            return ["not", ["=", ref, val]]
        if op in ("=", "~", ">", ">=", "<", "<="):
            return [op, ref, val]
        return ["=", ref, val]

    def build_rule(self, match_type: str, rules: list[dict], pinned_certnames: list[str]):
        """Compose a PE classifier rule from dynamic rules + pinned certnames."""
        dynamic = None
        if rules:
            joiner = "and" if (match_type or "all") == "all" else "or"
            dynamic = [joiner, *[self._translate_rule(r) for r in rules]]
        pinned = None
        if pinned_certnames:
            pinned = ["or", *[["=", ["trusted", "certname"], c] for c in pinned_certnames]]
        if dynamic and pinned:
            return ["or", pinned, dynamic]
        return dynamic or pinned

    async def create_node_group(
        self, name, description=None, environment="production",
        parent_id=None, match_type="all", rules=None, pinned_certnames=None,
    ) -> str:
        if not self._host:
            return ""
        hdrs = await self._token_hdr()
        group_id = str(uuid.uuid4())
        payload = {
            "id": group_id,
            "name": name,
            "environment": environment or "production",
            "parent": parent_id or self.ROOT_GROUP,
            "classes": {},
            "rule": self.build_rule(match_type, rules or [], pinned_certnames or []),
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

    async def update_node_group(
        self, group_id, name=None, description=None, environment=None,
        match_type="all", rules=None, pinned_certnames=None,
    ) -> None:
        """Update an existing PE classifier group's rule/environment/metadata."""
        if not self._host or not group_id:
            return
        hdrs = await self._token_hdr()
        payload = {"rule": self.build_rule(match_type, rules or [], pinned_certnames or [])}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if environment is not None:
            payload["environment"] = environment
        async with httpx.AsyncClient(verify=False) as c:
            try:
                r = await c.post(
                    f"{self._rbac()}/classifier-api/v1/groups/{group_id}",
                    json=payload,
                    headers={**hdrs, "Content-Type": "application/json"},
                    timeout=10,
                )
                if r.status_code not in (200, 201, 303):
                    r.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError(f"Puppet update node group failed: {e}") from e

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
