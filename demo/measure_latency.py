#!/usr/bin/env python3
"""Measure detection and closed-loop remediation latency over N trials.

Run this ON THE PLATFORM HOST (so the event's server-side `created_at` and the
injection time share one clock). For each trial it: resets the node to a
compliant baseline, injects the drift over SSH, then polls the platform API for

  • detection latency  = event.created_at  −  injection time
  • remediation latency = (moment remediation_outcome flips to success) − injection

and reports median / p95 for the thesis latency table. Use --loop off to
measure the scheduled-sweep contrast (no auto-remediation; the correction waits
for the next sweep/manual enforce).

Config (env or flags):
  CRICLO_API   base API URL, e.g. https://platform.local/api   (--api)
  CRICLO_KEY   an X-API-Key with operator rights                (--key)
  CRICLO_NODE  the node hostname as registered                  (--node)
  CRICLO_SSH   ssh target that can run the demo scripts, e.g. mallory@10.0.0.5 (--ssh)
  DEMO_DIR     demo dir on the node (default /opt/criclo-demo)   (--demo-dir)
  TRIALS       number of trials (default 10)                     (--trials)

Only Python stdlib is used.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone


def _iso_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def api_get(api: str, key: str, path: str) -> list | dict:
    req = urllib.request.Request(api.rstrip("/") + path, headers={"X-API-Key": key})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE          # demo platforms often use a self-signed cert
    with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
        return json.loads(r.read().decode())


def ssh(target: str, command: str) -> None:
    subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=accept-new", target, command],
        check=True, capture_output=True, text=True,
    )


def newest_events(api, key, node_id, limit=10):
    try:
        return api_get(api, key, f"/detection/events?node_id={node_id}&limit={limit}")
    except Exception:
        return []


def resolve_node_id(api, key, hostname):
    for n in api_get(api, key, "/nodes"):
        if n.get("hostname") == hostname or n.get("id") == hostname:
            return n["id"]
    raise SystemExit(f"node '{hostname}' not found via the API")


def percentile(values, p):
    if not values:
        return float("nan")
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def one_trial(args, node_id):
    demo = args.demo_dir
    loop = args.loop
    # 1) Reset to a compliant baseline for this control (idempotent).
    ssh(args.ssh, f"sudo CRICLO_LOOP=on {demo}/40_criclo_correct.sh >/dev/null 2>&1 || true")
    time.sleep(args.settle)
    seen = {e["id"] for e in newest_events(args.api, args.key, node_id)}

    # 2) Inject the drift; the platform's clock stamps the event.
    t0 = _iso_utc_now()
    ssh(args.ssh, f"sudo {demo}/30_inject_drift.sh >/dev/null 2>&1")

    # 3) Wait for the new detection event.
    detect = None
    ev = None
    deadline = time.time() + args.timeout
    while time.time() < deadline:
        for e in newest_events(args.api, args.key, node_id):
            if e["id"] not in seen and "sshd_config" in (e.get("path") or ""):
                ev = e
                detect = (_parse(e["created_at"]) - t0).total_seconds()
                break
        if ev:
            break
        time.sleep(args.poll)
    if ev is None:
        return None  # no event within timeout

    # 4) For the closed loop, wait until this change's remediation confirms.
    remediate = None
    if loop == "on":
        while time.time() < deadline:
            cur = next((e for e in newest_events(args.api, args.key, node_id) if e["id"] == ev["id"]), None)
            if cur and cur.get("remediation_outcome") in ("success", "skipped"):
                remediate = (_iso_utc_now() - t0).total_seconds()
                break
            time.sleep(args.poll)
    return {"detection": detect, "remediation": remediate,
            "violation": ev.get("violation"), "event_id": ev["id"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default=os.environ.get("CRICLO_API", ""))
    ap.add_argument("--key", default=os.environ.get("CRICLO_KEY", ""))
    ap.add_argument("--node", default=os.environ.get("CRICLO_NODE", ""))
    ap.add_argument("--ssh", default=os.environ.get("CRICLO_SSH", ""))
    ap.add_argument("--demo-dir", default=os.environ.get("DEMO_DIR", "/opt/criclo-demo"))
    ap.add_argument("--trials", type=int, default=int(os.environ.get("TRIALS", "10")))
    ap.add_argument("--loop", choices=["on", "off"], default="on")
    ap.add_argument("--poll", type=float, default=0.25)
    ap.add_argument("--settle", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=180.0)
    ap.add_argument("--csv", default="criclo_latency.csv")
    args = ap.parse_args()
    for req in ("api", "key", "node", "ssh"):
        if not getattr(args, req):
            sys.exit(f"missing --{req} (or CRICLO_{req.upper()})")

    node_id = resolve_node_id(args.api, args.key, args.node)
    print(f"Node {args.node} → {node_id}; {args.trials} trials, loop={args.loop}\n")

    det, rem = [], []
    with open(args.csv, "w") as fh:
        fh.write("trial,detection_s,remediation_s,violation\n")
        for i in range(1, args.trials + 1):
            r = one_trial(args, node_id)
            if not r:
                print(f"  trial {i:2d}: no event within timeout — skipped")
                continue
            if r["detection"] is not None:
                det.append(r["detection"])
            if r["remediation"] is not None:
                rem.append(r["remediation"])
            print(f"  trial {i:2d}: detection={r['detection']:.2f}s "
                  f"remediation={('%.2f s' % r['remediation']) if r['remediation'] is not None else '—':>8} "
                  f"violation={r['violation']}")
            fh.write(f"{i},{r['detection']:.3f},"
                     f"{'' if r['remediation'] is None else '%.3f' % r['remediation']},{r['violation']}\n")

    def report(name, xs):
        if not xs:
            print(f"  {name}: no data")
            return
        print(f"  {name}: median={statistics.median(xs):.2f}s  "
              f"p95={percentile(xs, 0.95):.2f}s  min={min(xs):.2f}s  max={max(xs):.2f}s  n={len(xs)}")

    print("\nResults (fill Table 5.3):")
    report("Detection latency  ", det)
    report("Remediation latency", rem)
    print(f"\nPer-trial CSV → {args.csv}")


if __name__ == "__main__":
    main()
