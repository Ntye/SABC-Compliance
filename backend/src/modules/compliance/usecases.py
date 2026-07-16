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
    ComplianceReport, Node, Notification, RemediationEvent,
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
            "detection_enrolled": node.detection_enrolled,
            "scan_ready": node.scan_ready,
            "reports": [
                {
                    "id": r.id, "source": r.source, "framework": r.framework,
                    "score": r.score, "passed_checks": r.passed_checks,
                    "failed_checks": r.failed_checks, "total_checks": r.total_checks,
                    "skipped_checks": r.skipped_checks, "profile": r.profile,
                    "duration": r.duration, "severity_counts": r.severity_counts,
                    "details": r.details,
                    "profile_id": r.profile_id, "profile_version": r.profile_version,
                    "compliance_group_id": r.compliance_group_id,
                    "tier_id": r.tier_id, "tier_name": r.tier_name,
                    "os_family": r.os_family,
                    "collected_at": r.collected_at.isoformat(),
                }
                for r in reports
            ],
            "remediations": [
                {
                    "id": r.id, "outcome": r.outcome, "resources_fixed": r.resources_fixed,
                    "triggered_at": r.triggered_at.isoformat(),
                    "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                    "detection_event_id": r.detection_event_id, "puppet_job_id": r.puppet_job_id,
                }
                for r in remediations
            ],
        }


class GetComplianceHistoryUseCase:
    """Scan history for the History tab — lightweight rows (no control details),
    newest first, for a single node or the whole fleet, within an optional
    collected_at window. Each row is tagged with its node hostname so the fleet
    view and CSV/JSON interval exports are self-describing."""

    def __init__(self, node_repo: INodeRepository, compliance_repo: IComplianceRepository) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo

    async def execute(
        self, node_id: str | None = None, since: str | None = None,
        until: str | None = None, limit: int = 1000,
    ) -> list[dict]:
        resolved_id = None
        if node_id:
            node = await _resolve_node(self._nodes, node_id)
            resolved_id = node.id
        rows = await self._repo.find_history(
            node_id=resolved_id, since=since, until=until, limit=limit)
        hostnames = {n.id: n.hostname for n in await self._nodes.find_all({})}
        for r in rows:
            r["hostname"] = hostnames.get(r["node_id"], r["node_id"])
        return rows


class GetComplianceReportUseCase:
    """One historical scan report by id, with full control details — for viewing
    or exporting a specific past scan (any node)."""

    def __init__(self, node_repo: INodeRepository, compliance_repo: IComplianceRepository) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo

    async def execute(self, report_id: str) -> dict:
        report = await self._repo.find_report(report_id)
        if report is None:
            raise NotFoundError(f"Scan report '{report_id}' not found")
        node = await self._nodes.find_by_id(report.node_id)
        return {
            "id": report.id, "node_id": report.node_id,
            "hostname": node.hostname if node else report.node_id,
            "ip": node.ip if node else None,
            "os_family": report.os_family or (node.os_family if node else None),
            "source": report.source, "framework": report.framework,
            "score": report.score, "passed_checks": report.passed_checks,
            "failed_checks": report.failed_checks, "total_checks": report.total_checks,
            "skipped_checks": report.skipped_checks, "severity_counts": report.severity_counts,
            "profile": report.profile, "profile_id": report.profile_id,
            "profile_version": report.profile_version, "tier_name": report.tier_name,
            "compliance_group_id": report.compliance_group_id,
            "duration": report.duration, "details": report.details,
            "collected_at": report.collected_at.isoformat(),
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
        scan_resolver=None,
    ) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo
        self._ssh = ssh
        self._default_key = default_ssh_key_path
        self._profile_path = profile_path
        self._scan_bin = scan_bin or self.SCAN_BIN
        # ScanEngineUseCase — used to install the scan engine on demand.
        self._scan_engine_ctrl = scan_ctrl
        # ScanPlanResolver — when set, scans resolve applicable profiles via the
        # node's compliance-group memberships and applicable controls via its
        # tier + OS family (Section 6). Absent → legacy single-profile scan.
        self._resolver = scan_resolver

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

        if self._resolver is not None:
            # Section 6: scan each profile the node's compliance groups bind, but
            # only the controls its tier makes applicable, in its OS family. Each
            # report is tagged with the group/profile+version/tier/family context.
            plan = await self._resolver.for_node(node)
            reports, last_reason = await self.scan_plan(node, plan)
            collected.extend(reports)
            if not collected:
                raise ValidationError(
                    last_reason
                    or "No applicable controls resolved for this node's tier/groups."
                )
        else:
            # Legacy single-profile path (back-compat).
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

    async def scan_plan(self, node: Node, plan) -> tuple[list[dict], str | None]:
        """Run every spec in a resolved NodeScanPlan, persist and summarise each
        report. Returns (summaries, last_skip_reason). Shared by the single-node
        scan and the compliance-group scan."""
        collected: list[dict] = []
        last_reason: str | None = None
        for spec in plan.specs:
            report, reason = await self._collect_scan(node, spec=spec, plan=plan)
            if report:
                await self._repo.save_report(report)
                collected.append(self._summarise(report))
            else:
                last_reason = reason
        return collected, last_reason

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

    async def _collect_scan(
        self, node: Node, spec=None, plan=None
    ) -> tuple[ComplianceReport | None, str | None]:
        """Run an InSpec profile against the node and parse JSON output.

        When *spec* is given (Section 6), the spec's generated InSpec directory
        is executed, narrowed to the tier/family-applicable controls via
        ``--controls``, and the resulting report is tagged with the
        group/profile+version/tier/os_family context. Otherwise the bundled
        default profile is run whole (legacy path).

        Returns ``(report, None)`` on success, or ``(None, reason)`` when the
        scan is skipped or fails so the caller can surface a clear error.
        """
        profile_path = (spec.inspec_dir if spec and spec.inspec_dir else self._profile_path)
        if not profile_path or not os.path.isdir(profile_path):
            return None, (
                f"Scan profile not found at {profile_path or '(unset)'} — "
                "the profile is missing from the deployment."
            )
        if spec is not None and not spec.applicable_control_ids:
            # Nothing is in scope for this node's tier/family on this profile —
            # not an error, just an empty spec the caller skips.
            return None, (
                f"No controls applicable for profile '{spec.profile_name}' at tier "
                f"'{plan.tier_name if plan else ''}' / family '{node.os_family}'."
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
            scan_bin, "exec", profile_path,
            "-t", target,
            "-i", key,
            "--port", str(node.ssh_port),
            "--reporter", "json",
            "--no-color", "--no-distinct-exit",
        ]
        # Section 6: run only the tier/family-applicable controls.
        if spec is not None and spec.applicable_control_ids:
            args.append("--controls")
            args.extend(spec.applicable_control_ids)
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

        report = self._scan_to_report(node, data, spec=spec)
        if not report:
            return None, "Compliance scan returned no controls."
        # Section 6: stamp the scan context so "which servers scanned against
        # standard X, at what tier" is a query.
        if spec is not None:
            report.profile = spec.profile_name
            report.profile_id = spec.profile_id
            report.profile_version = spec.profile_version
            report.compliance_group_id = spec.compliance_group_id
        if plan is not None:
            report.tier_id = plan.tier_id
            report.tier_name = plan.tier_name
            report.os_family = plan.os_family
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

    def _scan_to_report(self, node: Node, data: dict, spec=None) -> ComplianceReport | None:
        details: list[dict] = []
        passed = failed = skipped = 0

        # numeric section key → heading title, from the resolved spec's profile.
        sec_titles: dict[str, str] = getattr(spec, "section_titles", None) or {}

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
                # CIS Level (1|2) rides on the generated control's `tag cis_level`
                # — surface it so the tier that made the control in-scope is
                # visible in the detail view and every export.
                cis_level = tags.get("cis_level")
                try:
                    cis_level = int(cis_level) if cis_level is not None else None
                except (TypeError, ValueError):
                    cis_level = None

                if status == "pass":
                    passed += 1
                elif status == "fail":
                    failed += 1
                else:
                    skipped += 1

                # Group under the referential's own named sections. The control
                # id's numeric ancestors ("1", "1.1", "1.1.1") name each folder
                # level from the section-title map; the top level names the
                # section group (never "Other" when the referential has it).
                cid = ctrl.get("id")
                num = [p for p in str(cid or "").split(".") if p.isdigit()]
                ancestors = [".".join(num[:i]) for i in range(1, len(num))]
                ctrl_sections = {k: sec_titles[k] for k in ancestors if k in sec_titles}
                top_key = num[0] if num else ""
                # Top-level group name: the referential's own top section row if it
                # has one, else the CIS section name (the referential's top-level
                # numbering is CIS-aligned), so it never collapses to "Other".
                top_name = sec_titles.get(top_key) or _CIS_SECTIONS.get(top_key)
                section = f"{top_key} · {top_name}" if top_name else _cis_section(frameworks.get("cis"))

                details.append({
                    "control_id": cid,
                    "title": (ctrl.get("title") or cid or "").strip(),
                    "status": status,
                    "severity": severity,
                    "impact": impact,
                    "cis_level": cis_level,
                    "frameworks": frameworks,
                    "section": section,
                    "section_titles": ctrl_sections,
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


class ScanComplianceGroupUseCase:
    """Scan every member of a compliance group against the group's bound
    profiles — the uniform unit of scanning (Section 6).

    For each member node, each bound profile is scanned with only the controls
    the node's tier makes applicable, in the node's OS family. Every report is
    tagged with the group/profile+version/tier/family context.
    """

    def __init__(self, group_repo, node_repo: INodeRepository, resolver, collect_uc) -> None:
        self._groups = group_repo
        self._nodes = node_repo
        self._resolver = resolver
        self._collect = collect_uc

    async def execute(self, group_id: str) -> dict:
        group = await self._groups.find_by_id(group_id)
        if not group:
            raise NotFoundError(f"Compliance group '{group_id}' not found")

        plans = await self._resolver.for_group(group)
        nodes_out: list[dict] = []
        scanned = failed = 0
        for plan in plans:
            node = await self._nodes.find_by_id(plan.node_id)
            if node is None:
                continue
            try:
                reports, reason = await self._collect.scan_plan(node, plan)
                if reports:
                    scanned += 1
                    nodes_out.append({
                        "node_id": node.id, "hostname": node.hostname,
                        "os_family": plan.os_family, "tier": plan.tier_name,
                        "reports": len(reports),
                    })
                else:
                    failed += 1
                    nodes_out.append({
                        "node_id": node.id, "hostname": node.hostname,
                        "os_family": plan.os_family, "tier": plan.tier_name,
                        "reports": 0, "reason": reason,
                    })
            except Exception as exc:
                failed += 1
                logger.error("Group scan: node %s failed: %s", node.hostname, exc)
                nodes_out.append({"node_id": node.id, "hostname": node.hostname,
                                  "reports": 0, "error": str(exc)})
        return {
            "compliance_group_id": group.id,
            "compliance_group": group.name,
            "profiles": group.profile_ids,
            "members": len(group.node_ids),
            "scanned": scanned,
            "failed": failed,
            "nodes": nodes_out,
        }


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
        detection_event_id: str | None = None,
    ) -> dict:
        node = await _resolve_node(self._nodes, id_or_hostname)

        event = RemediationEvent(
            id=str(uuid.uuid4()),
            node_id=node.id,
            puppet_job_id="ssh-puppet-run",
            triggered_at=datetime.utcnow(),
            detection_event_id=detection_event_id,
        )

        if not node.puppet_enrolled:
            event.outcome = "skipped"
            event.completed_at = datetime.utcnow()
            await self._repo.save_remediation(event)
            return {
                "id": event.id, "node_id": node.id, "detection_event_id": detection_event_id,
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
                "id": event.id, "node_id": node.id, "detection_event_id": detection_event_id,
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
            "detection_event_id": detection_event_id,
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
        detection_event_id: str | None = None,
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
                return await self._process_node(nid, desc, rescan, detection_event_id)

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
        self, node_id: str, description: str, rescan: bool, detection_event_id: str | None
    ) -> dict:
        await self._broadcast(node_id, "closed_loop_started", {"message": "Enforcement starting."})
        entry: dict = {"node_id": node_id, "status": "success"}
        try:
            enforce = await self._remediate.execute(
                node_id, description=description, detection_event_id=detection_event_id,
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


class EnforceReferentialUseCase:
    """Enforce the SABC hardening referential on a node — or every member of a
    node group — so the internal referential fully passes.

    Where the closed loop runs whatever catalog the master already assigns,
    THIS makes the generated ``sabc_hardening`` module land and apply directly:
    an Ansible job pushes the module to the node and runs ``puppet apply``,
    scoped to exactly the controls the node's TIER and OS family make applicable
    (the same set the scan checks). Enforce → scan therefore converges on 100%.

    Applying the tier is implicit: the applicable-control set already encodes the
    tier's level gating, so enforcing it *is* applying the tiering to the target.

    Exactly one of ``node_id`` / ``group_id`` must be supplied. Group membership
    resolves through the injected ``get_group_uc`` (GetNodeGroupUseCase), which
    returns ``(group, [member_node_ids])`` — no cross-module import.
    """

    PLAYBOOK = "enforce_referential.yml"

    def __init__(
        self,
        node_repo: INodeRepository,
        start_job_uc,                 # StartJobUseCase
        scan_resolver,                # ScanPlanResolver
        profile_repo,                 # IProfileRepository
        module_src: str,
        get_group_uc=None,            # GetNodeGroupUseCase
        notification_repo=None,       # INotificationRepository
        collect_uc=None,              # CollectNodeComplianceUseCase
    ) -> None:
        self._nodes = node_repo
        self._start = start_job_uc
        self._resolver = scan_resolver
        self._profiles = profile_repo
        self._module_src = module_src
        self._get_group = get_group_uc
        self._notifications = notification_repo
        self._collect = collect_uc
        # control_id → puppet class key, cached per profile across a run.
        self._key_maps: dict[str, dict[str, str]] = {}

    async def execute(
        self,
        node_id: str | None = None,
        group_id: str | None = None,
        notify_on_complete: bool = False,
        control_ids: list[str] | None = None,
        on_complete=None,
    ) -> dict:
        """Enforce the referential on a node or group.

        ``control_ids`` restricts the applied subset to those referential
        controls (intersected with the node's tier-and-family scope) instead of
        the whole tier-applicable set — this is what the closed loop uses to
        remediate *only* the control(s) that drifted. ``on_complete`` is an
        ``async (job, node)`` callback invoked per launched job; the closed loop
        passes one to close its remediation window when the scoped run finishes.
        """
        if bool(node_id) == bool(group_id):
            raise ValidationError("Provide exactly one of node_id or group_id.")

        if group_id:
            if self._get_group is None:
                raise ValidationError("Group enforcement is not available (no group resolver).")
            group, member_ids = await self._get_group.execute(group_id)
            target = {"kind": "group", "id": group_id, "name": group.name}
            node_ids = list(dict.fromkeys(member_ids))
        else:
            node = await _resolve_node(self._nodes, node_id)
            target = {"kind": "node", "id": node.id, "name": node.hostname}
            node_ids = [node.id]

        self._key_maps.clear()
        jobs: list[dict] = []
        launched = skipped = 0
        for nid in node_ids:
            node = await self._nodes.find_by_id(nid)
            if node is None:
                jobs.append({"node_id": nid, "status": "skipped",
                             "reason": "node not found"})
                skipped += 1
                continue

            keys = await self._resolve_keys(node, only=control_ids)
            if not keys:
                jobs.append({"node_id": nid, "hostname": node.hostname,
                             "status": "skipped",
                             "reason": ("none of the requested controls are in "
                                        "this node's tier-and-family scope"
                                        if control_ids else
                                        "no tier-applicable controls resolved")})
                skipped += 1
                continue

            job = await self._start.execute({
                "type": "enforce_referential",
                "node_id": nid,
                "playbook": self.PLAYBOOK,
                "extra_vars": {
                    "sabc_module_src": self._module_src,
                    "sabc_controls": keys,
                },
                "on_complete": on_complete or (self._on_complete if notify_on_complete else None),
            })
            jobs.append({"node_id": nid, "hostname": node.hostname,
                         "status": "launched", "job_id": job.id,
                         "controls": len(keys)})
            launched += 1

        return {
            "target": target,
            "requested": len(node_ids),
            "launched": launched,
            "skipped": skipped,
            "jobs": jobs,
        }

    # ── Tiers-page chain: notify when the job lands, then scan + notify ───────

    async def _on_complete(self, job, node) -> None:
        """Runs when an enforcement job launched with ``notify_on_complete``
        finishes: record a platform notification with the job outcome, then
        launch the follow-up compliance scan and record its outcome too."""
        hostname = node.hostname if node else (job.node_id or "node")
        succeeded = job.status == "success"
        await self._notify(
            kind="enforcement",
            severity="success" if succeeded else "error",
            title=(f"Enforcement complete on {hostname}" if succeeded
                   else f"Enforcement failed on {hostname}"),
            message=(f"Referential enforcement job finished with status "
                     f"'{job.status}' (exit {job.exit_code}). "
                     + ("Launching verification scan."
                        if succeeded and self._collect is not None
                        else "Verification scan skipped.")),
            node_id=node.id if node else job.node_id,
            job_id=job.id,
        )
        if not (succeeded and node is not None and self._collect is not None):
            return

        try:
            result = await self._collect.execute(node.id)
            collected = result.get("collected") or []
            primary = next(
                (c for c in collected if c.get("source") != "puppet"),
                collected[0] if collected else None,
            )
            score = primary.get("score") if primary else None
            await self._notify(
                kind="scan",
                severity="success",
                title=f"Post-enforcement scan complete on {hostname}",
                message=(f"Compliance scan finished"
                         + (f" — score {score}%." if score is not None else ".")
                         + f" {len(collected)} report(s) collected."),
                node_id=node.id,
                job_id=job.id,
            )
        except Exception as exc:
            logger.error("Post-enforcement scan failed for %s: %s", hostname, exc)
            await self._notify(
                kind="scan",
                severity="error",
                title=f"Post-enforcement scan failed on {hostname}",
                message=str(exc),
                node_id=node.id,
                job_id=job.id,
            )

    async def _notify(self, *, kind: str, severity: str, title: str,
                      message: str, node_id: str | None, job_id: str | None) -> None:
        if self._notifications is None:
            return
        try:
            await self._notifications.save(Notification(
                id=str(uuid.uuid4()), title=title, message=message,
                kind=kind, severity=severity, node_id=node_id, job_id=job_id,
            ))
        except Exception as exc:  # a notification failure must never break the chain
            logger.error("Failed to record notification '%s': %s", title, exc)

    async def _resolve_keys(self, node: Node, only: list[str] | None = None) -> list[str]:
        """The sabc_hardening class keys applicable to *node* (tier × family).

        When *only* is given, restrict to those referential control ids
        (intersected with the tier-and-family scope), so the closed loop can
        apply just the control(s) that drifted rather than the whole set.
        """
        plan = await self._resolver.for_node(node)
        only_set = set(only) if only else None
        keys: list[str] = []
        seen: set[str] = set()
        for spec in plan.specs:
            key_map = await self._key_map(spec.profile_id)
            for cid in spec.applicable_control_ids:
                if only_set is not None and cid not in only_set:
                    continue
                key = key_map.get(cid)
                if key and key not in seen:
                    seen.add(key)
                    keys.append(key)
        return sorted(keys)

    async def _key_map(self, profile_id: str) -> dict[str, str]:
        cached = self._key_maps.get(profile_id)
        if cached is not None:
            return cached
        from modules.profiles.artifact_generator import puppet_key
        profile = await self._profiles.find_by_id(profile_id)
        mapping: dict[str, str] = {}
        if profile is not None:
            for c in profile.controls:
                if c.control_id:
                    mapping[c.control_id] = puppet_key(c)
        self._key_maps[profile_id] = mapping
        return mapping
