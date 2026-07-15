# Measuring enforcement, detection, and closed-loop time

Every number you need is already timestamped by the platform. Here is where each
one lives and the exact formula, plus how to get medians/p95 automatically.

## The three times

| Metric | Definition | From … |
|---|---|---|
| **Detection time** | injected change → orchestrator receives the event | detection event's `created_at` − injection time |
| **Enforcement time** | one Puppet convergence run | remediation `completed_at` − `triggered_at` (a scan/enforce job's own duration) |
| **Closed-loop time** | detected deviation → confirmed correction | the moment the event's `remediation_outcome` becomes `success` − event `created_at` (this is detection ⊕ enforcement ⊕ confirming re-scan) |

### Where the timestamps come from

- **Detection event** — `GET /api/detection/events?node_id=<id>`: each row has
  `timestamp` (agent-side, when the change was seen on the node) and
  `created_at` (server-side, when the orchestrator received it). It also now
  carries `violation` (true/false/null) and `remediation_outcome`.
- **Remediation / enforcement run** — a `RemediationEvent` has `triggered_at`
  and `completed_at`; the difference is the Puppet-run (enforcement) time. The
  compliance report produced by a scan carries its own `duration`.
- **Confirming re-scan** — `GET /api/compliance/history?node_id=<id>` lists every
  scan with `collected_at`; the first green scan after the correction confirms it.

## The fastest way: read it off the History tab

For a single, on-camera measurement:
1. Note the wall-clock second you run `30_inject_drift.sh`.
2. Open **Detection Events** → the new event's timestamp is the receipt; the
   detection time is that minus your injection second.
3. When the event flips to **Resolved**, that is the closed-loop confirmation;
   the closed-loop time is confirmation minus the event time.
4. The **enforcement time** alone is the remediation/job duration shown on the
   node's remediation history (or the scan's `duration` on the History tab).

## The repeatable way: `measure_latency.py`

Run it **on the platform host** (so the event's `created_at` and the injection
time share one clock). It resets the node, injects the drift, and polls the API,
N times, then prints median/p95 and writes a per-trial CSV.

```bash
export CRICLO_API=https://platform.local/api
export CRICLO_KEY=sabc_...            # operator API key
export CRICLO_NODE=web-01             # node hostname
export CRICLO_SSH=mallory@10.0.0.5    # can run the demo scripts on the node
export DEMO_DIR=/opt/criclo-demo

# closed loop (node enforced + loop ON):
python3 measure_latency.py --trials 20 --loop on

# scheduled-sweep contrast at the same tier (loop OFF — no auto-remediation;
# the correction waits for the next sweep/manual enforce):
python3 measure_latency.py --trials 20 --loop off
```

Output → detection-latency median/p95 and remediation-latency median/p95, plus
`criclo_latency.csv`. Those four numbers populate Table 5.3; the loop-on vs
loop-off contrast at equal tier is exactly the effect of Axis 3.

> Note on clocks: detection latency uses the server's `created_at` minus the
> injection instant recorded on the same host — no node/server clock skew.
> Closed-loop latency is measured by the poller's wall clock (±`--poll`, default
> 0.25 s). Keep the platform host's clock in NTP sync for clean numbers.
