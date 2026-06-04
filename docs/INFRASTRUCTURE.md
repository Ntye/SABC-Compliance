# Infrastructure lifecycle & failure-scenario handling

This document maps the Puppet + Wazuh install lifecycle to the **automatic
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

### Wazuh manager (`install_wazuh_manager.yml`)
| Scenario | Handling |
|----------|----------|
| Memory shortage (indexer OOM) | ⚠️ Preflight warns (<4 GB), continues |
| Disk space | ⚠️ Preflight warns (<20 GB on `/`), continues |
| Port conflicts (1514/1515/55000/443/9200) | ⚠️ Preflight lists any existing listeners |
| Incorrect repository / no internet | ✅ Online vs. airgap auto-detected; 📋 offline-package steps printed |
| API / indexer / dashboard bring-up | ✅ Waits for API port 55000; verifies `wazuh-control` |

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

### Wazuh agent (`install_wazuh_agent.yml`)
| Scenario | Handling |
|----------|----------|
| Manager unreachable | 📋 Preflight **blocks** if 1514/1515 unreachable, prints causes |
| Firewall blocking ports | 📋 Same preflight block + `nc -vz` verification hint |
| Incorrect manager address | ✅ `WAZUH_MANAGER` env + `ossec.conf <address>` both set |
| Agent ID conflict (VM clone) | ✅ Self-heal: resets `client.keys`, re-enrolls once if not connected |
| Registration key / handshake | ✅ Confirms “Connected to the server” in `ossec.log` |
| Time sync | ✅ chrony installed + stepped |

---

## 3. Network, DNS & PKI (cross-cutting)

- **DNS** — the Node Registry **DNS check** (⚠ button) verifies resolution in
  every direction (platform↔node, node→puppet, node→wazuh) and pre-fills the
  exact `/etc/hosts` fix. Playbooks also self-add host entries during install.
- **Firewall / routing** — connectivity preflights fail **before** install with
  a boxed remediation block rather than hanging mid-run.
- **PKI** — stale/duplicate/expired certs from cloning or reinstalls are
  detected from the first-run output and recovered automatically (Puppet `ca
  clean` + ssl reset; Wazuh `client.keys` reset), then re-enrolled exactly once.

---

## 4. Beyond the installer (operator-owned)

These lifecycle areas from the design notes are **operational**, not install-time,
and are intentionally out of the installer's scope (monitored via Puppet/Wazuh
themselves once enrolled):

- Configuration drift detection & correction (Puppet catalog runs)
- Ongoing monitoring, alert tuning, missing/excessive alerts (Wazuh rules)
- Resource saturation over time (CPU/memory/disk growth)
- Security posture (unauthorized/compromised agents, manager hardening)
- High availability / failover and multi-site / hybrid-cloud topology

The installer's job is to get every node **cleanly enrolled and reporting**;
the two platforms own the steady-state lifecycle from there.
