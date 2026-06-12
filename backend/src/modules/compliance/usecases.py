from __future__ import annotations
import asyncio
import json
import os
import re
import shutil
import uuid
from datetime import datetime

from core.domain.entities import ComplianceReport, Node, RemediationEvent
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
            "inspec_installed": node.inspec_installed,
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
    Run a structured InSpec compliance scan against an enrolled node.

    The bundled CIS Benchmark profile is executed from the controller over
    InSpec's agentless ssh:// transport — every control carries an impact score,
    a severity, a CIS section and framework references (CIS / ISO 27001 /
    PCI-DSS). There is no shell fallback: this is a complete InSpec scan or a
    clear, actionable error. When ``auto_install`` is set and InSpec is missing
    from the controller, it is installed on demand so the operator can scan
    directly from the compliance page.

    The Puppet last-run summary is collected as a supplementary report when the
    Puppet agent is enrolled.

    Gated on the node being Puppet/Wazuh enrolled so the UI only starts showing
    data once the node is part of the managed infrastructure.
    """

    INSPEC_BIN = "/usr/bin/inspec"

    def __init__(
        self,
        node_repo: INodeRepository,
        compliance_repo: IComplianceRepository,
        ssh: ISSHClient,
        default_ssh_key_path: str = "",
        profile_path: str = "",
        inspec_bin: str | None = None,
        inspec_ctrl=None,
    ) -> None:
        self._nodes = node_repo
        self._repo = compliance_repo
        self._ssh = ssh
        self._default_key = default_ssh_key_path
        self._profile_path = profile_path
        self._inspec_bin = inspec_bin or self.INSPEC_BIN
        # InspecControllerUseCase — used to install InSpec on demand.
        self._inspec_ctrl = inspec_ctrl

    def _inspec_available(self) -> bool:
        return bool(
            os.path.isfile(self._inspec_bin) or shutil.which("inspec")
        )

    async def execute(self, id_or_hostname: str, auto_install: bool = True) -> dict:
        node = await _resolve_node(self._nodes, id_or_hostname)

        if not (node.puppet_enrolled or node.wazuh_enrolled):
            raise ValidationError(
                "Node is not enrolled with Puppet or Wazuh yet — enroll it from the "
                "Infrastructure page before collecting compliance data."
            )

        # Ensure InSpec is present on the controller; install on demand so the
        # operator can scan directly from the compliance page.
        if not self._inspec_available():
            if auto_install and self._inspec_ctrl is not None:
                install = await self._inspec_ctrl.install_on_controller()
                if not (install.get("installed") or install.get("success")):
                    raise ValidationError(
                        "InSpec is not installed on the platform and automatic "
                        "installation failed: " + (install.get("error") or "unknown error")
                    )
            else:
                raise ValidationError(
                    "InSpec is not installed on the platform. Install it from the "
                    "compliance page (Install InSpec) to run compliance scans."
                )

        collected: list[dict] = []

        # Complete, structured InSpec scan — no shell fallback.
        inspec_report, inspec_reason = await self._collect_inspec(node)
        if not inspec_report:
            raise ValidationError(inspec_reason or "The InSpec scan did not produce any results.")

        await self._repo.save_report(inspec_report)
        collected.append(self._summarise(inspec_report))
        if not node.inspec_installed:
            node.inspec_installed = True
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

    # ── InSpec scan ───────────────────────────────────────────────────────────

    async def _collect_inspec(self, node: Node) -> tuple[ComplianceReport | None, str | None]:
        """Run the bundled InSpec profile against the node and parse JSON output.

        Returns ``(report, None)`` on success, or ``(None, reason)`` when the
        scan is skipped or fails so the caller can surface why it fell back to
        the shell spot-check.
        """
        if not self._profile_path or not os.path.isdir(self._profile_path):
            return None, (
                f"InSpec profile not found at {self._profile_path or '(unset)'} — "
                "the bundled profile is missing from the deployment."
            )

        # Resolve the InSpec binary; the configured path may differ per install.
        inspec_bin = self._inspec_bin
        if not os.path.isfile(inspec_bin):
            inspec_bin = shutil.which("inspec") or inspec_bin
        if not (os.path.isfile(inspec_bin) or shutil.which("inspec")):
            return None, (
                "InSpec is not installed on the platform — install it from the "
                "Infrastructure page to enable structured compliance scans."
            )

        key = node.ssh_key_path or self._default_key
        target = f"ssh://{node.ssh_user}@{node.ip}"
        args = [
            inspec_bin, "exec", self._profile_path,
            "-t", target,
            "-i", key,
            "--port", str(node.ssh_port),
            "--reporter", "json",
            "--chef-license", "accept-silent",
            "--no-color", "--no-distinct-exit",
        ]
        # Most controls need root to read /etc/shadow, auditd state, etc.
        if (node.ssh_user or "").strip() != "root":
            args.append("--sudo")

        env = {**os.environ, "CHEF_LICENSE": "accept-silent"}
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=240)
        except FileNotFoundError:
            return None, "InSpec binary could not be executed on the platform."
        except asyncio.TimeoutError:
            return None, "InSpec scan timed out after 240s (node slow or unreachable)."
        except Exception as exc:
            return None, f"InSpec scan failed to start: {exc}"

        raw = (stdout or b"").decode(errors="replace").strip()
        data = self._extract_json(raw)
        if not data:
            err = (stderr or b"").decode(errors="replace").strip()
            snippet = (err or raw or "no output")[-400:]
            return None, f"InSpec produced no parseable output: {snippet}"

        report = self._inspec_to_report(node, data)
        if not report:
            return None, "InSpec scan returned no controls."
        return report, None

    @staticmethod
    def _extract_json(raw: str) -> dict | None:
        """InSpec may emit a license/info banner before the JSON document."""
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

    def _inspec_to_report(self, node: Node, data: dict) -> ComplianceReport | None:
        framework_keys = ("cis", "iso27001", "iso_27001", "pci_dss", "pci-dss", "nist")
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
                frameworks = {
                    ("pci_dss" if k == "pci-dss" else k): v
                    for k, v in tags.items()
                    if k in framework_keys and v
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
            source="inspec",
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

    async def execute(self, id_or_hostname: str, description: str | None = None) -> dict:
        node = await _resolve_node(self._nodes, id_or_hostname)

        event = RemediationEvent(
            id=str(uuid.uuid4()),
            node_id=node.id,
            puppet_job_id="ssh-puppet-run",
            triggered_at=datetime.utcnow(),
        )

        if not node.puppet_enrolled:
            event.outcome = "skipped"
            event.completed_at = datetime.utcnow()
            await self._repo.save_remediation(event)
            return {
                "id": event.id, "outcome": event.outcome, "resources_fixed": 0,
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
            return {"id": event.id, "outcome": "failed", "resources_fixed": 0, "message": str(exc)}

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
            "outcome": event.outcome,
            "resources_fixed": event.resources_fixed,
            "message": "Puppet enforcement run complete.",
        }
