# Infrastructure lifecycle & failure-scenario handling

This document maps the Puppet + detection-agent install lifecycle to the **automatic
preflight checks** and **self-healing** the platform performs, so installs
succeed across the common failure scenarios instead of failing opaquely.

Legend: ✅ handled automatically · ⚠️ detected & warned · 📋 operator action
(the job log prints exact remediation).

---

## 1. Initial installation

### Puppet master (`install_puppet_master.yml`)
| Scenario | Handling |
|----------|----------|
| Insufficient RAM | ⚠️ Preflight warns (<6 GB PE / <2.5 GB open-source), continues |
| Disk space exhaustion | ⚠️ Preflight warns (<20 GB on `/opt` for PE), continues |
| Java install issues | ✅ Java 17 installed for the chosen mode (PE bundles its own) |
| Package/dependency conflicts | ✅ Online / local-package / PE-tarball modes auto-selected |
| DNS hostname mismatch | ✅ `certname`/`server` pinned to FQDN in `puppet.conf` |
| Service startup / cert gen | ✅ Waits for port 8140; verifies version; reports console URL |

---

## 2. Agent enrollment

### Puppet agent (`install_puppet_agent.yml`)
| Scenario | Handling |
|----------|----------|
| DNS resolution failure | ✅ `/etc/hosts` entry added for the master FQDN |
| Network/connectivity (refused) | 📋 Preflight **blocks** if 8140 unreachable, prints causes |
| Firewall on 8140 | 📋 Same preflight block + `nc -vz` verification hint |
| Certificate not signed | ✅ Waits for CSR, signs on master automatically |
| SSL mismatch (reinstalled server/agent) | ✅ Self-heal: detects, cleans cert both ends, re-enrolls once |
| Time sync (`cert not yet valid`) | ✅ chrony installed + `chronyc makestep` before cert ops |

### Detection agent (`install_detection_agent.yml`)
| Scenario | Handling |
|----------|----------|
| Gateway unreachable at install | ⚠️ Install proceeds; the agent spools events locally and flushes on reconnect |
| Missing python3 / watchdog | ✅ Installed from the distro repo, falling back to pip |
| Wrong gateway address / API key | ✅ Both injected from platform config at install time |
| Service startup | ✅ systemd unit enabled + started; active state verified |

---

## 3. Network, DNS & PKI (cross-cutting)

- **DNS** — the Node Registry **DNS check** (⚠ button) verifies resolution in
  every direction (platform↔node, node→puppet) and pre-fills the exact
  `/etc/hosts` fix. Playbooks also self-add host entries during install.
- **Firewall / routing** — connectivity preflights fail **before** install with
  a boxed remediation block rather than hanging mid-run.
- **PKI** — stale/duplicate/expired certs from cloning or reinstalls are
  detected from the first-run output and recovered automatically (Puppet `ca
  clean` + ssl reset), then re-enrolled exactly once.

---

## 4. Beyond the installer (operator-owned)

These lifecycle areas from the design notes are **operational**, not install-time,
and are intentionally out of the installer's scope (handled by Puppet and the
detection agent once enrolled):

- Configuration drift detection & correction (detection agent + Puppet catalog runs)
- Ongoing monitoring and event triage (Detection Events page)
- Resource saturation over time (CPU/memory/disk growth)
- Security posture (unauthorized/compromised agents, manager hardening)
- High availability / failover and multi-site / hybrid-cloud topology

The installer's job is to get every node **cleanly enrolled and reporting**;
Puppet and the detection agent own the steady-state lifecycle from there.
