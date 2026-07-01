from __future__ import annotations
import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

from core.domain.entities import (
    CIS_BENCHMARK_PROFILE_ID, INTERNAL_PROFILE_ID,
    ComplianceReport, Node, RemediationEvent,
)
from core.domain.interfaces import (
    IComplianceRepository, INodeRepository, ISSHClient,
)
from core.errors import NotFoundError, ValidationError


# CIS Benchmark top-level sections, used to group controls in the UI.
_CIS_SECTIONS = {
    "1": "Initial Setup",
    "2": "Services",
    "3": "Network Configuration",
    "4": "Logging & Auditing",
    "5": "Access, Authentication & Authorization",
    "6": "System Maintenance",
}


def _cis_section(cis_id: str | None) -> str:
    """Map a CIS control id like '5.2.8' to a section label '5 · Access…'."""
    if not cis_id:
        return "Other"
    top = str(cis_id).split(".")[0].strip()
    name = _CIS_SECTIONS.get(top)
    return f"{top} · {name}" if name else "Other"


async def _resolve_node(repo: INodeRepository, id_or_hostname: str) -> Node:
    node = await repo.find_by_id(id_or_hostname)
    if not node:
        node = await repo.find_by_hostname(id_or_hostname)
    if not node:
        raise NotFoundError(f"Node '{id_or_hostname}' not found")
    return node


class GetComplianceSummaryUseCase:
    """Fleet-wide compliance overview — one row per node with latest reports."""

    def __init__(self, compliance_repo: IComplianceRepository) -> None:
        self._repo = compliance_repo

    async def execute(self) -> list[dict]:
        return await self._repo.find_summary()


class GetNodeComplianceUseCase:
    """Full compliance detail for a single node: reports (with controls) + remediations."""

    def __init__(self, node_repo: INodeRepository, compliance_repo: IComplianceRepository) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo

    async def execute(self, id_or_hostname: str) -> dict:
        node = await _resolve_node(self._nodes, id_or_hostname)
        reports = await self._repo.find_by_node(node.id)
        remediations = await self._repo.find_remediations(node.id)

        return {
            "node_id": node.id,
            "hostname": node.hostname,
            "ip": node.ip,
            "os_family": node.os_family,
            "status": node.status,
            "puppet_enrolled": node.puppet_enrolled,
            "wazuh_enrolled": node.wazuh_enrolled,
            "scan_ready": node.scan_ready,
            "reports": [
                {
                    "id": r.id, "source": r.source, "framework": r.framework,
                    "score": r.score, "passed_checks": r.passed_checks,
                    "failed_checks": r.failed_checks, "total_checks": r.total_checks,
                    "skipped_checks": r.skipped_checks, "profile": r.profile,
                    "duration": r.duration, "severity_counts": r.severity_counts,
                    "details": r.details,
                    "collected_at": r.collected_at.isoformat(),
                }
                for r in reports
            ],
            "remediations": [
                {
                    "id": r.id, "outcome": r.outcome, "resources_fixed": r.resources_fixed,
                    "triggered_at": r.triggered_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "wazuh_alert_id": r.wazuh_alert_id, "puppet_job_id": r.puppet_job_id,
                }
                for r in remediations
            ],
        }


class CollectNodeComplianceUseCase:
    """
    Run a structured compliance scan against an enrolled node using CINC Auditor.

    The bundled CIS Benchmark profile is executed from the controller over an
    agentless ssh:// transport — every control carries an impact score, a
    severity, and a CIS section reference. There is no shell fallback: this is
    a complete scan or a clear, actionable error. When ``auto_install`` is set
    and the scan engine is missing from the controller, it is installed on demand
    so the operator can scan directly from the compliance page.

    The Puppet last-run summary is collected as a supplementary report when the
    Puppet agent is enrolled.
    """

    SCAN_BIN = "/usr/bin/cinc-auditor"

    def __init__(
        self,
        node_repo: INodeRepository,
        compliance_repo: IComplianceRepository,
        ssh: ISSHClient,
        default_ssh_key_path: str = "",
        profile_path: str = "",
        scan_bin: str | None = None,
        scan_ctrl=None,
    ) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo
        self._ssh = ssh
        self._default_key = default_ssh_key_path
        self._profile_path = profile_path
        self._scan_bin = scan_bin or self.SCAN_BIN
        # ScanEngineUseCase — used to install the scan engine on demand.
        self._scan_engine_ctrl = scan_ctrl

    def _scan_engine_available(self) -> bool:
        return bool(
            os.path.isfile(self._scan_bin) or shutil.which("cinc-auditor")
        )

    async def execute(
        self, id_or_hostname: str, auto_install: bool = True, profile_id: str | None = None
    ) -> dict:
        node = await _resolve_node(self._nodes, id_or_hostname)

        # Ensure the scan engine is present on the controller; install on demand
        # so the operator can scan directly from the compliance page.
        if not self._scan_engine_available():
            if auto_install and self._scan_engine_ctrl is not None:
                install = await self._scan_engine_ctrl.install_on_controller()
                if not (install.get("installed") or install.get("success")):
                    raise ValidationError(
                        "CINC Auditor is not installed on the platform and automatic "
                        "installation failed: " + (install.get("error") or "unknown error")
                    )
            else:
                raise ValidationError(
                    "CINC Auditor is not installed on the platform. Install it from the "
                    "compliance page to run compliance scans."
                )

        collected: list[dict] = []

        # Complete, structured compliance scan — no shell fallback.
        scan_report, scan_reason = await self._collect_scan(node)
        if not scan_report:
            raise ValidationError(scan_reason or "The compliance scan did not produce any results.")

        self._apply_profile(scan_report, profile_id)
        await self._repo.save_report(scan_report)
        collected.append(self._summarise(scan_report))
        if not node.scan_ready:
            node.scan_ready = True
            node.updated_at = datetime.utcnow()
            try:
                await self._nodes.update(node)
            except Exception:
                pass

        # Supplementary Puppet enforcement summary.
        if node.puppet_enrolled:
            puppet_report = await self._collect_puppet(node)
            if puppet_report:
                await self._repo.save_report(puppet_report)
                collected.append(self._summarise(puppet_report))

        return {"node_id": node.id, "collected": collected}

    def _summarise(self, r: ComplianceReport) -> dict:
        return {
            "id": r.id, "source": r.source, "framework": r.framework, "score": r.score,
            "passed_checks": r.passed_checks, "failed_checks": r.failed_checks,
            "total_checks": r.total_checks, "skipped_checks": r.skipped_checks,
            "profile": r.profile, "duration": r.duration,
            "severity_counts": r.severity_counts,
            "collected_at": r.collected_at.isoformat(),
        }

    @staticmethod
    def _apply_profile(report: ComplianceReport, profile_id: str | None) -> None:
        """Override report profile/framework labels based on the operator's selection."""
        if profile_id == CIS_BENCHMARK_PROFILE_ID:
            report.profile = "CIS Benchmark"
            report.framework = "cis"
        elif profile_id == INTERNAL_PROFILE_ID:
            report.profile = "SABC Linux Baseline"
            report.framework = "internal"

    # ── Compliance scan ────────────────────────────────────────────────────────

    async def _collect_scan(self, node: Node) -> tuple[ComplianceReport | None, str | None]:
        """Run the bundled CIS profile against the node and parse JSON output.

        Returns ``(report, None)`` on success, or ``(None, reason)`` when the
        scan is skipped or fails so the caller can surface a clear error.
        """
        if not self._profile_path or not os.path.isdir(self._profile_path):
            return None, (
                f"Scan profile not found at {self._profile_path or '(unset)'} — "
                "the bundled profile is missing from the deployment."
            )

        # Resolve the scan binary; the configured path may differ per install.
        scan_bin = self._scan_bin
        if not os.path.isfile(scan_bin):
            scan_bin = shutil.which("cinc-auditor") or scan_bin
        if not (os.path.isfile(scan_bin) or shutil.which("cinc-auditor")):
            return None, (
                "CINC Auditor is not installed on the platform — install it from the "
                "Infrastructure page to enable compliance scans."
            )

        key = node.ssh_key_path or self._default_key
        target = f"ssh://{node.ssh_user}@{node.ip}"
        args = [
            scan_bin, "exec", self._profile_path,
            "-t", target,
            "-i", key,
            "--port", str(node.ssh_port),
            "--reporter", "json",
            "--no-color", "--no-distinct-exit",
        ]
        # Most controls need root to read /etc/shadow, auditd state, etc.
        if (node.ssh_user or "").strip() != "root":
            args.append("--sudo")

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=240)
        except FileNotFoundError:
            return None, "CINC Auditor binary could not be executed on the platform."
        except asyncio.TimeoutError:
            return None, "Compliance scan timed out after 240s (node slow or unreachable)."
        except Exception as exc:
            return None, f"Compliance scan failed to start: {exc}"

        raw = (stdout or b"").decode(errors="replace").strip()
        data = self._extract_json(raw)
        if not data:
            err = (stderr or b"").decode(errors="replace").strip()
            # An unreachable node is the most common cause: surface it clearly
            # instead of dumping the raw "no parseable output" engine log.
            transport = self._ssh_transport_error(f"{err}\n{raw}")
            if transport:
                return None, (
                    f"Cannot establish an SSH connection to {node.ip}:{node.ssh_port} "
                    f"(user '{node.ssh_user}'): {transport}. Verify the node is online, "
                    "the SSH service is running on that port, and the platform's SSH key "
                    "is authorized for this user."
                )
            snippet = (err or raw or "no output")[-400:]
            return None, f"Scan produced no parseable output: {snippet}"

        report = self._scan_to_report(node, data)
        if not report:
            return None, "Compliance scan returned no controls."
        return report, None

    @staticmethod
    def _ssh_transport_error(text: str) -> str | None:
        """Detect an SSH transport failure in the scan engine output.

        CINC Auditor reports an unreachable node in its train ssh backend log
        (e.g. ``Errno::ECONNREFUSED``, ``connection failed``, ``SSH session
        could not be established``) rather than as JSON. Map those signatures to
        a short, human-readable cause so the operator gets an actionable error.
        """
        if not text:
            return None
        low = text.lower()
        causes = [
            ("econnrefused", "connection refused"),
            ("connection refused", "connection refused"),
            ("etimedout", "connection timed out"),
            ("connection timed out", "connection timed out"),
            ("ehostunreach", "host unreachable"),
            ("no route to host", "host unreachable"),
            ("authentication failed", "authentication failed"),
            ("permission denied", "authentication failed (permission denied)"),
            ("host key verification failed", "host key verification failed"),
        ]
        for needle, label in causes:
            if needle in low:
                return label
        # Generic train/ssh transport failure with no specific errno.
        if (
            "can't connect to 'ssh' backend" in low
            or "ssh session could not be established" in low
            or "[ssh] connection failed" in low
        ):
            return "SSH session could not be established"
        return None

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        """The scan engine may emit a license/info banner before the JSON document."""
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            pass
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(raw[start:end + 1])
        except Exception:
            return None

    @staticmethod
    def _severity(impact: float) -> str:
        if impact >= 0.7:
            return "high"
        if impact >= 0.4:
            return "medium"
        if impact > 0:
            return "low"
        return "info"

    def _scan_to_report(self, node: Node, data: dict) -> ComplianceReport | None:
        details: list[dict] = []
        passed = failed = skipped = 0

        profile_name: str | None = None
        for prof in data.get("profiles") or []:
            profile_name = profile_name or prof.get("name")
            for ctrl in prof.get("controls") or []:
                results = ctrl.get("results") or []
                statuses = [r.get("status") for r in results]
                if not statuses or all(s == "skipped" for s in statuses):
                    status = "skip"
                elif "failed" in statuses:
                    status = "fail"
                else:
                    status = "pass"

                impact = float(ctrl.get("impact") or 0)
                severity = self._severity(impact)

                message = ""
                for r in results:
                    if r.get("status") == "failed":
                        message = (r.get("message") or r.get("code_desc") or "").strip()
                        break
                if not message and status == "skip" and results:
                    message = (results[0].get("skip_message") or results[0].get("message") or "").strip()

                tags = ctrl.get("tags") or {}
                # Only extract the CIS framework tag; all other framework tags are ignored.
                frameworks = {
                    k: v
                    for k, v in tags.items()
                    if k == "cis" and v
                }

                if status == "pass":
                    passed += 1
                elif status == "fail":
                    failed += 1
                else:
                    skipped += 1

                details.append({
                    "control_id": ctrl.get("id"),
                    "title": (ctrl.get("title") or ctrl.get("id") or "").strip(),
                    "status": status,
                    "severity": severity,
                    "impact": impact,
                    "frameworks": frameworks,
                    "section": _cis_section(frameworks.get("cis")),
                    "desc": (ctrl.get("desc") or "").strip()[:600],
                    "message": message[:600],
                })

        if not details:
            return None

        stats = data.get("statistics") or {}
        duration = stats.get("duration") if isinstance(stats, dict) else None

        return ComplianceReport(
            id=str(uuid.uuid4()),
            node_id=node.id,
            source="scan",
            framework="cis",
            passed_checks=passed,
            failed_checks=failed,
            total_checks=passed + failed,
            skipped_checks=skipped,
            details=details,
            profile=profile_name or "sabc-linux-baseline",
            duration=float(duration) if isinstance(duration, (int, float)) else None,
            collected_at=datetime.utcnow(),
        )

    async def _collect_puppet(self, node: Node) -> ComplianceReport | None:
        summary_path = "/opt/puppetlabs/puppet/cache/state/last_run_summary.yaml"
        try:
            stdout, _, rc = await self._ssh.run_command(
                node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path,
                f"sudo cat {summary_path} 2>/dev/null || cat {summary_path} 2>/dev/null",
            )
        except Exception:
            return None
        if not stdout.strip():
            return None

        # Parse the `resources:` block of last_run_summary.yaml
        def _num(key: str) -> int:
            m = re.search(rf"{key}:\s*(\d+)", stdout)
            return int(m.group(1)) if m else 0

        total = _num("total")
        failed = _num("failed") + _num("failed_to_restart")
        changed = _num("changed")
        if total == 0:
            return None

        passed = max(total - failed, 0)
        details = [
            {"control_id": "puppet.total",   "title": "Resources managed by Puppet", "status": "info", "value": total},
            {"control_id": "puppet.changed", "title": "Resources changed last run",  "status": "info", "value": changed},
            {"control_id": "puppet.failed",  "title": "Resources failed last run",   "status": "fail" if failed else "pass", "value": failed},
        ]
        return ComplianceReport(
            id=str(uuid.uuid4()),
            node_id=node.id,
            source="puppet",
            framework="cis",
            passed_checks=passed,
            failed_checks=failed,
            total_checks=total,
            details=details,
            collected_at=datetime.utcnow(),
        )


class TriggerRemediationUseCase:
    """
    Trigger remediation on a node. When the Puppet agent is enrolled this runs
    `puppet agent -t` over SSH (a real enforcement run); otherwise the event is
    recorded as skipped. The RemediationEvent is persisted either way so the
    node's history reflects the attempt.
    """

    def __init__(self, node_repo: INodeRepository, compliance_repo: IComplianceRepository, ssh: ISSHClient) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo
        self._ssh = ssh

    async def execute(
        self,
        id_or_hostname: str,
        description: str | None = None,
        wazuh_alert_id: str | None = None,
    ) -> dict:
        node = await _resolve_node(self._nodes, id_or_hostname)

        event = RemediationEvent(
            id=str(uuid.uuid4()),
            node_id=node.id,
            puppet_job_id="ssh-puppet-run",
            triggered_at=datetime.utcnow(),
            wazuh_alert_id=wazuh_alert_id,
        )

        if not node.puppet_enrolled:
            event.outcome = "skipped"
            event.completed_at = datetime.utcnow()
            await self._repo.save_remediation(event)
            return {
                "id": event.id, "node_id": node.id, "wazuh_alert_id": wazuh_alert_id,
                "outcome": event.outcome, "resources_fixed": 0,
                "message": "Node has no Puppet agent — nothing to enforce. Enroll Puppet first.",
            }

        await self._repo.save_remediation(event)

        try:
            stdout, stderr, rc = await self._ssh.run_command(
                node.ip, node.ssh_port, node.ssh_user, node.ssh_key_path,
                "sudo /opt/puppetlabs/bin/puppet agent -t --detailed-exitcodes 2>&1 || true",
            )
        except Exception as exc:
            event.outcome = "failed"
            event.completed_at = datetime.utcnow()
            await self._repo.update_remediation(event)
            return {
                "id": event.id, "node_id": node.id, "wazuh_alert_id": wazuh_alert_id,
                "outcome": "failed", "resources_fixed": 0, "message": str(exc),
            }

        out = stdout or ""
        # Count enforced resources from the run output
        changed = len(re.findall(r"changed '.*' to '.*'", out)) or len(
            re.findall(r"\bcurrent_value\b", out)
        )
        m = re.search(r"Applied catalog.*?(\d+)\s+resources", out)
        # detailed-exitcodes: 0 = no changes, 2 = changes applied, 4/6 = failures
        had_failure = bool(re.search(r"\bErr(?:or)?\b|Failed to apply catalog", out))
        event.outcome = "failed" if had_failure else "success"
        event.resources_fixed = changed
        event.completed_at = datetime.utcnow()
        await self._repo.update_remediation(event)

        return {
            "id": event.id,
            "node_id": node.id,
            "wazuh_alert_id": wazuh_alert_id,
            "outcome": event.outcome,
            "resources_fixed": event.resources_fixed,
            "message": "Puppet enforcement run complete.",
        }


class RunClosedLoopUseCase:
    """Drive the closed remediation loop for a SINGLE node OR a NODE GROUP.

    For each target node the loop is: Puppet enforcement (`puppet agent -t` over
    SSH, via TriggerRemediationUseCase) → optional compliance re-scan (CINC/InSpec,
    via CollectNodeComplianceUseCase) so the dashboard reflects the post-fix
    posture. Group runs fan out across members with bounded concurrency so a
    large group doesn't open dozens of simultaneous SSH sessions.

    Exactly one of ``node_id`` / ``group_id`` must be supplied. Group membership
    is resolved through the injected ``get_group_uc`` (GetNodeGroupUseCase),
    which returns ``(group, [member_node_ids])`` — no cross-module import.
    """

    def __init__(
        self,
        node_repo: INodeRepository,
        remediate_uc: "TriggerRemediationUseCase",
        collect_uc: "CollectNodeComplianceUseCase | None" = None,
        get_group_uc=None,
        event_bus=None,
        ws_manager=None,
        concurrency: int = 4,
    ) -> None:
        self._nodes = node_repo
        self._remediate = remediate_uc
        self._collect = collect_uc
        self._get_group = get_group_uc
        self._bus = event_bus
        self._ws = ws_manager
        self._concurrency = max(1, concurrency)

    async def execute(
        self,
        node_id: str | None = None,
        group_id: str | None = None,
        description: str | None = None,
        rescan: bool = True,
        wazuh_alert_id: str | None = None,
    ) -> dict:
        if bool(node_id) == bool(group_id):
            raise ValidationError("Provide exactly one of node_id or group_id.")

        # ── Resolve the target node list ──────────────────────────────────────
        if group_id:
            if self._get_group is None:
                raise ValidationError("Group remediation is not available (no group resolver).")
            group, member_ids = await self._get_group.execute(group_id)
            target = {"kind": "group", "id": group_id, "name": group.name}
            node_ids = list(dict.fromkeys(member_ids))  # de-dup, preserve order
            if not node_ids:
                return {
                    "target": target, "requested": 0, "processed": 0,
                    "succeeded": 0, "failed": 0, "skipped": 0,
                    "message": f"Group '{group.name}' has no member nodes to remediate.",
                    "nodes": [],
                }
        else:
            node = await _resolve_node(self._nodes, node_id)
            target = {"kind": "node", "id": node.id, "name": node.hostname}
            node_ids = [node.id]

        desc = description or (
            f"Closed-loop remediation ({target['kind']} {target['name']})"
        )

        # ── Fan out with bounded concurrency ──────────────────────────────────
        sem = asyncio.Semaphore(self._concurrency)

        async def _one(nid: str) -> dict:
            async with sem:
                return await self._process_node(nid, desc, rescan, wazuh_alert_id)

        results = await asyncio.gather(
            *[_one(nid) for nid in node_ids], return_exceptions=True
        )

        nodes_out: list[dict] = []
        succeeded = failed = skipped = 0
        for nid, res in zip(node_ids, results):
            if isinstance(res, Exception):
                logger.error("Closed loop crashed for node %s: %s", nid, res)
                nodes_out.append({"node_id": nid, "status": "failed", "error": str(res)})
                failed += 1
                continue
            nodes_out.append(res)
            if res["status"] == "success":
                succeeded += 1
            elif res["status"] == "skipped":
                skipped += 1
            else:
                failed += 1

        summary = {
            "target": target,
            "requested": len(node_ids),
            "processed": len(nodes_out),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "rescan": rescan and self._collect is not None,
            "nodes": nodes_out,
        }
        self._publish("compliance.closed_loop_completed", {
            "target": target, "succeeded": succeeded, "failed": failed, "skipped": skipped,
        })
        return summary

    async def _process_node(
        self, node_id: str, description: str, rescan: bool, wazuh_alert_id: str | None
    ) -> dict:
        await self._broadcast(node_id, "closed_loop_started", {"message": "Enforcement starting."})
        entry: dict = {"node_id": node_id, "status": "success"}
        try:
            enforce = await self._remediate.execute(
                node_id, description=description, wazuh_alert_id=wazuh_alert_id,
            )
            entry["enforcement"] = enforce
            outcome = (enforce or {}).get("outcome")
            if outcome == "skipped":
                entry["status"] = "skipped"
            elif outcome == "failed":
                entry["status"] = "failed"
            await self._broadcast(node_id, "enforcement_completed", enforce)

            # Re-scan only when enforcement actually ran (not skipped/failed).
            if rescan and self._collect is not None and entry["status"] == "success":
                await self._broadcast(node_id, "rescan_started", {"message": "Re-scanning."})
                try:
                    scan = await self._collect.execute(node_id)
                    entry["rescan"] = scan
                    await self._broadcast(node_id, "rescan_completed", {
                        "collected": scan.get("collected") if isinstance(scan, dict) else None,
                    })
                except Exception as exc:
                    # A re-scan failure must not mask a successful enforcement.
                    logger.error("Post-remediation re-scan failed for %s: %s", node_id, exc)
                    entry["rescan_error"] = str(exc)
                    await self._broadcast(node_id, "rescan_failed", {"error": str(exc)})
        except NotFoundError:
            raise
        except Exception as exc:
            logger.error("Enforcement failed for %s: %s", node_id, exc)
            entry["status"] = "failed"
            entry["error"] = str(exc)
            await self._broadcast(node_id, "closed_loop_failed", {"error": str(exc)})
        return entry

    def _publish(self, event_name: str, payload: dict) -> None:
        if self._bus is not None:
            try:
                self._bus.publish(event_name, payload)
            except Exception as exc:
                logger.error("Event publish failed [%s]: %s", event_name, exc)

    async def _broadcast(self, node_id: str, phase: str, payload: dict) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.broadcast_node(node_id, {
                "channel": "remediation",
                "phase": phase,
                "node_id": node_id,
                "timestamp": datetime.utcnow().isoformat(),
                "data": payload,
            })
        except Exception as exc:
            logger.error("WebSocket broadcast failed [%s/%s]: %s", node_id, phase, exc)
