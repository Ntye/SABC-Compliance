# CRICLO — Demo Filming Scenario & Voice-over

A shot-by-shot plan to record one continuous demonstration, from which every
figure in the *Experimentation and Results* chapter is a still frame. Scenes are
ordered as the chapter reads. Each scene gives: **Screen** (what is visible),
**Do** (the actions), **Grab** (the figure to freeze), and **Say** (voice-over).

**Setup before you hit record**
- Two windows side by side, both large-font: **(L)** the CRICLO web UI in a
  browser; **(R)** a terminal with two tabs — `platform` (host) and `node`
  (`ssh mallory@<node>`).
- Copy `demo/` to the node at `/opt/criclo-demo` and run `sudo ./00_prepare.sh`.
- Record at 1080p, 100% browser zoom, cursor highlight on. Pause ~2 s on each
  "Grab" so you have a clean frame. Keep each scene < 60 s.
- Have the environment facts ready to fill Table 5.1 (instance types, versions).

Legend for the figure labels: they match the `\label{…}` in the chapter.

---

## Act 0 — Cold open (≈20 s, no figure)

**Screen:** CRICLO dashboard, fleet at a glance.
**Say:** "This is CRICLO — a closed-loop Linux compliance platform. In the next
few minutes it will bring a server under management, measure it against the CIS
benchmark, harden it, and then catch and automatically undo a live intrusion —
telling us who did it and why it was blocked. Every action you see is audited."

---

## Act 1 — Onboarding, Provisioning, Environment (§5.1)

### Scene 1 — Bootstrap → `fig:bootstrap`
**Screen:** (L) Infrastructure → *Install agents* for the target node.
**Do:** Start the bootstrap; let the live job log stream.
**Grab:** the install in progress (job log visible). → **figures/bootstrap.png**
**Say:** "Bringing a node under management installs exactly two components — the
enforcement agent and the detection agent — from one bootstrap. The operator
does the same thing for every server; the difference between Debian and Red Hat
is resolved beneath this procedure, not exposed here."

### Scene 2 — Agents running → `fig:agents-running`
**Screen:** (R:node) `systemctl status puppet compliance-agent --no-pager`
(or the two unit names on your box).
**Do:** Show both services `active (running)`.
**Grab:** both agents active. → **figures/agents_running.png**
**Say:** "On the node the two agents are now live: Puppet, which enforces state,
and the detection agent, which watches configuration and only ever reports."

### Scene 3 — Enrolment & tier → `fig:enrollment`
**Screen:** (L) the node's page; assign a criticality tier.
**Do:** Open the tier selector; assign **Non-critical** (or Critical); note it
defaults to the most conservative tier; point to the audit entry.
**Grab:** enrolment + tier selection. → **figures/enrollment.png**
**Say:** "The node is registered and given a criticality tier — defaulting to
the most conservative until an operator decides otherwise. The assignment is an
audited action, and from here the node is validated on exactly the scope its
tier defines."

> Table 5.1 (environment): fill from your EC2 instance types and the versions
> printed by `puppet --version`, `cinc-auditor version`, `python3 --version`,
> your FastAPI/PostgreSQL/Docker versions.

---

## Act 2 — The Four Planes (§5.2)

### Scene 4 — Enforcement plane → `fig:puppet-catalog`
**Screen:** (L) node page → **Enforce**; (R:node) optionally
`journalctl -u puppet -f` or the run output.
**Do:** Click **Enforce**; watch the tier-scoped module apply. The posture score
climbs (this is your ~49% → ~88% moment — keep it for the results act too).
**Grab:** node converging / Puppet applying. → **figures/puppet_catalog.png**
**Say:** "Enforcement is Puppet, run masterless. From the node's resolved policy
the platform assembles a tier-scoped module and applies it. Each corrective is
guarded by the control's own check, so an already-compliant control is a no-op —
enforcement is convergent, not destructive."

> Listing `lst:puppet-class`: copy a representative class from the generated
> `sabc_hardening` module (e.g. the SSH `PermitRootLogin` class) — a code
> listing, taken from the repo, not the video.

### Scene 5 — Detection agent forwarding → `fig:detection-agent`
**Screen:** (R:node) tail the agent, then edit a watched file.
**Do:** `sudo journalctl -u compliance-agent -f`; in the node tab run
`sudo /opt/criclo-demo/30_inject_drift.sh`. Show the agent log line forwarding
the event for `/etc/ssh/sshd_config`.
**Grab:** the agent forwarding a change event. → **figures/detection_agent.png**
**Say:** "The detection agent watches the security-relevant configuration. The
moment `sshd_config` changes it computes a hash and metadata, attaches who made
the change, and forwards the event. It never edits the node — reporting only."

### Scene 6 — Events as evidence → `fig:detection-events`
**Screen:** (L) Detection Events page.
**Do:** Show the new event: path, type, timestamp, and **actor = mallory**.
**Grab:** events received and stored. → **figures/detection_events.png**
**Say:** "On the platform the change lands as evidence — the file, the kind of
change, the time, and the identity behind it. This is the ‘who' an auditor
needs, captured automatically."

### Scene 7 — Validation plane → `fig:validation-run`
**Screen:** (L) node → **Run scan** (default profile).
**Do:** Run the scan; open the per-control results; expand one pass and one
fail; show a **skipped** control's reason.
**Grab:** validation run + per-control verdicts. → **figures/validation_run.png**
**Say:** "Validation is CINC Auditor. Each control is a test written once, run
against the node for a pass or fail with evidence, and guarded so only the
family-correct check runs. The scope is the node's tier — it is scanned against
exactly the controls its tier defines."

> Listing `lst:inspec-control`: copy a representative control from the generated
> CINC profile — a code listing from the repo.

### Scene 8 — Dashboard overview → `fig:dashboard-overview`
**Screen:** (L) Compliance → fleet posture.
**Do:** Show the estate posture, KPIs, distribution.
**Grab:** fleet posture overview. → **figures/dashboard_overview.png**
**Say:** "The presentation plane consolidates all three into one posture — the
share of applicable controls passing across the estate, at a glance."

### Scene 9 — Per-node detail → `fig:dashboard-node`
**Screen:** (L) node compliance page — Posture tab, then History tab.
**Do:** Show scope, verdicts, the failures-by-severity breakdown, and the
change-history graph.
**Grab:** per-node compliance detail. → **figures/dashboard_node.png**
**Say:** "Per node we see its scope, every verdict, and its history of
configuration change over time — posture and provenance in one view."

### Scene 10 — Orchestrator runtime → `fig:orchestrator-runtime`
**Screen:** (R:platform) the API/orchestrator log; (L) trigger any action
(a scan or enforce) so a request/response and an ingested event flow through.
**Do:** Show a dispatched action and an ingested detection event at the single
endpoint.
**Grab:** the orchestrator brokering the planes. → **figures/orchestrator_runtime.png**
**Say:** "Underneath, the orchestrator brokers everything: it dispatches
enforcement and validation and routes their responses, and it ingests every
detection event at one endpoint, where the decision on each event is taken."

---

## Act 3 — Closed Loop, Tiers, Safety, End-to-End (§5.3)

### Scene 11 — Closed-loop wiring → `fig:loop-wiring`
**Screen:** split — (R:node) and (L) Detection Events + node page. Node tier is
**enforced** and **closed loop ON**.
**Do:** As `mallory`, `sudo /opt/criclo-demo/30_inject_drift.sh`. Watch: the
event arrives → the platform decides → run
`sudo CRICLO_LOOP=on /opt/criclo-demo/40_criclo_correct.sh`. Then re-scan → green.
**Grab:** the full cycle in one frame (event + correction). → **figures/loop_wiring.png**
**Say:** "Now the loop, end to end. A genuine change on a loop-active node
triggers an immediate, targeted remediation of just the affected control — in
addition to the next scheduled sweep. Detected, decided, corrected, confirmed."

### Scene 12 — Tiers as realised → `fig:tier-management`
**Screen:** (L) Tiers page.
**Do:** Show the two system tiers (Non-critical = L1, Critical = L1+2), a custom
tier, and the **independent** enforcement and closed-loop switches.
**Grab:** tier config + independent flags. → **figures/tier_management.png**
**Say:** "Criticality is three independent axes, not one ladder. The tier fixes
the validation scope. Whether controls are enforced, and whether the loop is
active, are two separate flags — set on the node or a group, never welded to the
tier."

### Scene 13 — Feedback-storm guard → `fig:safety-storm`
**Screen:** (L) Detection Events.
**Do:** Start an **Enforce** run and, *while it runs*, inject a drift. Show the
resulting writes recorded as **sanctioned/suppressed**, not a cascade of
remediations.
**Grab:** writes during enforcement marked sanctioned. → **figures/safety_storm.png**
**Say:** "A corrective writes to the very files we watch, so unguarded it would
re-enter the loop. Two guards stop that: a run-in-progress marker and a
suppression window. Here, changes made during an enforcement run are recorded as
sanctioned — the storm never starts."

### Scene 14 — Axis independence, live (supports `fig:tier-management` / §5.4.3)
**Screen:** split node + Detection Events.
**Do:** Set the node **loop OFF**; inject the drift; run
`sudo CRICLO_LOOP=off /opt/criclo-demo/40_criclo_correct.sh`. Show: **evidence
recorded, no correction**, and the author told it was *not* reverted. Then set
**loop ON** and repeat to show correction. (Optional B-roll for the discussion.)
**Say:** "Same drift, loop off: it is detected and recorded, but nothing is
touched — and the author is told it was logged, not reverted. Turn the loop on,
and the identical drift is corrected automatically. The axes are independent in
practice, not just on paper."

### Scene 15 — End-to-end remediation + PROOF → `fig:e2e`
**Screen:** three beats, node + platform.
**Do:**
1. **Baseline:** scan green for the SSH control.
2. **Deviation:** as `mallory`, `sudo /opt/criclo-demo/30_inject_drift.sh`.
3. **Detection & decision:** event with `actor=mallory` on the platform.
4. **Correction:** `sudo CRICLO_LOOP=on /opt/criclo-demo/40_criclo_correct.sh`.
5. **Proof on the node:** `grep -n PermitRootLogin /etc/ssh/sshd_config` — show
   the **commented offending line stamped with who + why**, and the compliant
   line restored; show the **author's SSH session receiving the `wall`
   notice** explaining why the change was blocked.
6. **Confirm:** re-scan → control green again.
**Grab:** the sequence (or a composite) — baseline, deviation, detection,
decision, correction, re-validation. → **figures/e2e_remediation.png**
**Say:** "One control, all the way through. Compliant baseline. Mallory enables
root SSH login — a clear violation. It is detected and attributed to her. With
the loop enabled the platform reverts it: the offending line is commented out
and kept as proof, stamped with who set it and which control it broke, the
secure setting is restored, and Mallory is told, in her own session, exactly why
her change was blocked. The re-scan confirms the control is green — drift to
proof in seconds."

---

## Act 4 — Results (§5.4) — reading the numbers

These figures are charts/tables built from measurements; film the screens you
read them from, then render the charts from your data.

### Scene 16 — Posture before/after → `fig:posture`, Table `tab:posture`
**Do:** Show the node at the **~49%** baseline (from `10_make_noncompliant.sh`),
then after **Enforce** at **~88%**. Read both numbers from the node page.
**Grab (screen):** before and after posture. → basis for **figures/posture_chart.png**
**Say:** "Measured on the Debian node: compliance rises from about forty-nine
percent before CRICLO acts to about eighty-eight percent after enforcement — the
share of applicable controls passing."

### Scene 17 — Latency → `fig:latency`, Table `tab:latency`
**Do:** From the detection event timestamp to the confirmed correction, read the
**closed-loop** remediation latency; contrast with the **scheduled-sweep** path
at the same tier (loop off, corrected at the next sweep).
**Grab (screen):** the History/timestamps you derive latency from. → basis for
**figures/latency_chart.png**
**Say:** "Detection is near-instant. Under the closed loop, correction completes
in seconds; at the same tier without the loop, the same deviation waits for the
next scheduled sweep. The contrast at equal tier is exactly the effect of the
loop, isolated from whether enforcement happens."

### Scene 18 — Factorial & by-tier (Tables `tab:factorial`, `tab:by-tier`)
**Do:** Walk the four enforcement×loop combinations at fixed scope, and the two
tiers, reading the observed behaviour off the platform for each. Use Scene 14's
recordings as evidence.
**Say:** "Across the factorial the behaviour is exactly as specified:
enforcement off, no correction whatever the loop; enforcement on, the loop
changes only the speed of correction; and validation returns a verdict in every
cell. Detection runs and records on every node, whatever its tier — while the
scanned scope follows the tier alone."

---

## Capture checklist (figure → scene)

| Figure | Scene |
|---|---|
| `fig:bootstrap` | 1 |
| `fig:agents-running` | 2 |
| `fig:enrollment` | 3 |
| `fig:puppet-catalog` | 4 |
| `fig:detection-agent` | 5 |
| `fig:detection-events` | 6 |
| `fig:validation-run` | 7 |
| `fig:dashboard-overview` | 8 |
| `fig:dashboard-node` | 9 |
| `fig:orchestrator-runtime` | 10 |
| `fig:loop-wiring` | 11 |
| `fig:tier-management` | 12 |
| `fig:safety-storm` | 13 |
| `fig:e2e` | 15 |
| `fig:posture` (chart) | 16 |
| `fig:latency` (chart) | 17 |

Listings `lst:puppet-class` and `lst:inspec-control` are code excerpts taken
from the generated `sabc_hardening` Puppet module and the CINC profile in the
repo, not from the video.
