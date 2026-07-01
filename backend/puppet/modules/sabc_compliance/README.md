# sabc_compliance — Puppet enforcement of the SABC internal referential

This Puppet module is the **enforcement half of the platform's closed
remediation loop**. Wazuh (or an operator) detects compliance drift against the
internal referential — a CIS Linux Benchmark — and the platform runs
`puppet agent -t`; the classes here bring the node back into compliance.

It maps the deterministic, safely-remediable controls of
`backend/scan-profiles/sabc-linux-baseline` (the referential the scanner checks)
to idempotent Puppet resources, using only Puppet core types (no external
modules) so it works on an airgapped master.

## Usage

```puppet
include sabc_compliance
```

or, tuned per node/group (e.g. via Hiera or an ENC):

```puppet
class { 'sabc_compliance':
  manage_firewall        => true,   # install + enable host firewall (SSH allowed first)
  purge_insecure_servers => false,  # remove apache/nfs/samba/… (opt-in)
  remove_other_nopasswd  => false,  # strip NOPASSWD from accounts != automation user
}
```

## What it enforces (by CIS section)

| Section | Enforced |
|---|---|
| 1 Initial Setup | ASLR/ptrace/suid_dumpable sysctl, filesystem-module blacklist, AIDE, prelink removal, bootloader perms, warning banners |
| 2 Services | time sync (chrony), xinetd + insecure clients removed, servers opt-in |
| 3 Network | full network sysctl hardening, uncommon-protocol blacklist, host firewall (SSH-safe) |
| 4 Logging/Audit | auditd install+enable, log sizing/retention, CIS watch rules, rsyslog |
| 5 Access/Auth | cron perms, **validated** sshd hardening drop-in, password policy (login.defs/pwquality/faillock), sudo NOPASSWD hygiene |
| 6 Maintenance | passwd/shadow/group file permissions |

## Safety model (read before changing defaults)

* **Idempotent & convergent** — every resource re-runs with no churn (verified
  with `puppet apply --noop`).
* **Never locks out access.** The sshd drop-in is validated with `sshd -t`; if
  the combined config is invalid the drop-in is removed and the run fails
  loudly. Password authentication is never disabled. The host firewall always
  allows the SSH port *before* it is enabled.
* **The `ansible` automation account is an approved exception** (referential
  control `sabc-5.3.5`): its passwordless sudo is **never** touched.
  `remove_other_nopasswd` only ever affects *other* accounts, and only after
  `visudo -c` validates the result — otherwise it is reverted.
* **Disruptive controls are opt-in** — removing server packages
  (`purge_insecure_servers`), restricting `su` (`restrict_su`) and stripping
  other accounts' NOPASSWD (`remove_other_nopasswd`) default to `false`.
* **Detective-only controls are not auto-remediated** — partition layout,
  world-writable/unowned files, duplicate UIDs, empty passwords and extra UID-0
  accounts stay visible in the scan report rather than being blindly "fixed",
  which on a live host is more dangerous than the finding.

## Validation

Every manifest passes `puppet parser validate`, and
`puppet apply --noop --modulepath=… -e 'include sabc_compliance'` compiles a
clean catalog (0 errors) in both the default and all-opt-in configurations.
