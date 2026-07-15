"""A watched-file change is an ALERT only when it makes a control regress.

The detection gateway re-scans after every genuine change and classifies it:
a control moving pass->fail is a violation (alert, and remediated when the loop
is on); a change that breaks nothing is benign evidence (no alert, no
remediation). Without a prior scan the impact is left unassessed (None).
"""
from __future__ import annotations

from datetime import datetime

from core.domain.entities import ConfigChangeEvent, Node
from modules.detection.usecases import ReceiveDetectionEventUseCase


class Rep:
    def __init__(self, fail_ids):
        self.details = [{"control_id": i, "status": "fail"} for i in fail_ids]


class FakeComplianceRepo:
    def __init__(self, reports):
        self.reports = list(reports)                 # newest first

    async def find_by_node(self, node_id):
        return list(self.reports)


class FakeCollect:
    """A scan that produces `after` as the newest report for the node."""
    def __init__(self, repo, after):
        self.repo, self.after, self.called = repo, after, False

    async def execute(self, node_id, **kw):
        self.called = True
        self.repo.reports.insert(0, self.after)
        return {"collected": ["scan"]}


class FakeDetectionRepo:
    def __init__(self):
        self.updates = []

    async def update_violation(self, event_id, violation, detail):
        self.updates.append((event_id, violation, detail))


class FakeRemediate:
    def __init__(self):
        self.called = False

    async def execute(self, node_id, **kw):
        self.called = True
        return {"outcome": "success", "resources_fixed": 1}


def _uc(compliance, collect, detection, remediate):
    return ReceiveDetectionEventUseCase(
        node_repo=None, detection_repo=detection, compliance_repo=compliance,
        remediate_uc=remediate, collect_uc=collect,
    )


NODE = Node(id="n1", hostname="web-01", ip="10.0.0.5")


def _event():
    return ConfigChangeEvent(id="e1", node_id="n1", path="/etc/ssh/sshd_config",
                             event_type="modified", timestamp=datetime.utcnow())


async def test_regression_is_a_violation_and_remediates():
    comp = FakeComplianceRepo([Rep({"5.1.a"})])            # before: one failing
    collect = FakeCollect(comp, Rep({"5.1.a", "5.2.b"}))   # after: a NEW failure
    det, rem = FakeDetectionRepo(), FakeRemediate()
    await _uc(comp, collect, det, rem)._assess_and_maybe_remediate(NODE, _event(), closed_loop=True)

    assert det.updates and det.updates[-1][0] == "e1"
    assert det.updates[-1][1] is True                      # violation
    assert "5.2.b" in det.updates[-1][2]                   # names the regressed control
    assert rem.called is True                              # loop on → corrected


async def test_benign_change_is_not_an_alert_and_is_not_remediated():
    comp = FakeComplianceRepo([Rep({"5.1.a"})])            # before
    collect = FakeCollect(comp, Rep({"5.1.a"}))            # after: identical failures
    det, rem = FakeDetectionRepo(), FakeRemediate()
    await _uc(comp, collect, det, rem)._assess_and_maybe_remediate(NODE, _event(), closed_loop=True)

    assert det.updates[-1][1] is False                     # benign
    assert rem.called is False                             # no correction for a benign change


async def test_benign_change_under_loop_off_is_still_benign():
    comp = FakeComplianceRepo([Rep(set())])
    collect = FakeCollect(comp, Rep(set()))
    det, rem = FakeDetectionRepo(), FakeRemediate()
    await _uc(comp, collect, det, rem)._assess_and_maybe_remediate(NODE, _event(), closed_loop=False)

    assert det.updates[-1][1] is False
    assert rem.called is False


async def test_no_baseline_is_unassessed_but_still_safe_under_loop():
    comp = FakeComplianceRepo([])                          # no prior scan
    collect = FakeCollect(comp, Rep({"5.1.a"}))
    det, rem = FakeDetectionRepo(), FakeRemediate()
    await _uc(comp, collect, det, rem)._assess_and_maybe_remediate(NODE, _event(), closed_loop=True)

    assert det.updates[-1][1] is None                      # can't prove a regression
    assert rem.called is True                              # fallback: still corrected under loop
