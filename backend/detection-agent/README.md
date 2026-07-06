# SABC Compliance Detection Agent

A single-file Python 3 daemon (`agent.py`) that runs on every managed node and
forms the **detection plane** of the SABC compliance platform. It watches the
compliance-critical configuration paths with inotify, snapshots every change
as **evidence** (never rollback), and reports to the platform gateway.

## What it does

1. **Watch** — inotify (via [`watchdog`](https://pypi.org/project/watchdog/),
   the only non-stdlib dependency) on the paths listed in
   `/etc/compliance-agent/config.yaml`. Directories are recursive; bursts of
   events on the same path are debounced (2 s window by default).
2. **Snapshot on change** — SHA-256 + `{mode, uid, gid, size, mtime}`, plus
   the file content (base64) when the per-path policy is `full`. A local hash
   cache provides `prev_hash` → `new_hash` on every event, and an initial
   baseline snapshot of all watched files is taken at first start.
   `hash-only` is forced for `/etc/shadow` and any `*key*` / `*.pem` / `*.crt`
   basename, so private material never leaves the node.
3. **Puppet-run guard** — if Puppet's agent lock file
   (`/opt/puppetlabs/puppet/cache/state/agent_catalog_run.lock`) is present,
   the event carries `puppet_running: true`. The agent **never suppresses
   locally** — the gateway decides.
4. **Actor enrichment** — best-effort `ausearch` lookup of the most recent
   write (`{auid, exe, comm}`); auditd is not a dependency (`actor: null`
   when unavailable).
5. **Send** — `POST /api/webhooks/detection` with the `X-API-Key` header,
   exponential-backoff retry (max 5 attempts), and a local spool file that
   drains FIFO once the gateway is reachable again.
6. **Heartbeat** — a lightweight `event_type: heartbeat` every 10 minutes so
   the platform can display agent last-seen.

## Event payload

```json
{
  "node_hostname": "web-01",
  "path": "/etc/ssh/sshd_config",
  "event_type": "modified",          // created|modified|deleted|baseline|heartbeat
  "timestamp": "2026-07-05T12:00:00+00:00",
  "prev_hash": "…",                  // null on first sight
  "new_hash": "…",                   // null on delete
  "file_meta": {"mode": "0o600", "uid": 0, "gid": 0, "size": 3210, "mtime": 1751712000.0},
  "content_b64": "…",                // only when policy = full
  "puppet_running": false,
  "actor": {"auid": 1000, "exe": "/usr/bin/vim.basic", "comm": "vim"}  // or null
}
```

## Install

The platform installs the agent via **Infrastructure → Agents → Detection
agent** (Ansible playbook `install_detection_agent.yml`), which copies
`agent.py` to `/usr/local/lib/compliance-agent/`, writes the config with the
gateway URL + API key injected from platform settings, installs the systemd
unit and starts `compliance-detection-agent`.

Manual install:

```bash
apt install python3-watchdog || pip3 install watchdog
install -D -m 0755 agent.py /usr/local/lib/compliance-agent/agent.py
install -D -m 0600 config.example.yaml /etc/compliance-agent/config.yaml  # edit it
install -D -m 0644 compliance-detection-agent.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now compliance-detection-agent
```

## Tests

```bash
python3 -m pytest detection-agent/tests -q
```

Covers the hash-only snapshot policy and the debounce logic (no watchdog or
network required — the module imports cleanly without them).
