# SABC CIS Linux Benchmark (InSpec profile)

This is the InSpec profile the SABC compliance platform runs against every
managed node to produce structured compliance reports. It implements a
comprehensive CIS-Benchmark-aligned baseline across all six CIS sections.

## How it runs

The platform invokes it **from the controller** over InSpec's agentless SSH
transport — no InSpec install is required on the managed nodes:

```bash
inspec exec sabc-linux-baseline \
  -t ssh://<user>@<host> \
  -i <ssh_key> --port <port> --sudo \
  --reporter json --chef-license accept-silent
```

There is **no shell fallback**: a scan is a complete InSpec run or a clear,
actionable error. If InSpec is not installed on the controller, the platform
installs it on demand so the operator can scan directly from the compliance
page.

The JSON output is parsed into `ComplianceReport` rows: every control becomes a
detail entry with its status (`pass`/`fail`/`skip`), an `impact` score, a derived
`severity` (high ≥ 0.7, medium ≥ 0.4, low > 0, info = 0), the CIS section and the
framework references declared via `tag`.

## Control catalogue

| File                      | CIS section | Coverage                                                    |
|---------------------------|-------------|-------------------------------------------------------------|
| `1_initial_setup.rb`      | 1           | Filesystem modules & partitions, AIDE, boot, ASLR, banners  |
| `2_services.rb`           | 2           | Time sync, removal of special-purpose services & clients    |
| `3_network.rb`            | 3           | Network sysctls, uncommon protocols, host firewall          |
| `4_logging_audit.rb`      | 4           | auditd, audit rules, rsyslog/journald, log permissions      |
| `5_access_auth.rb`        | 5           | cron/at, SSH hardening, PAM, password policy, su            |
| `6_maintenance.rb`        | 6           | System file permissions, user/group account hygiene         |

Every control is tagged with `cis`, and where applicable `iso27001` and
`pci_dss`, so reports can be filtered by framework.

## Extending / matching a specific CIS release

The controls follow the CIS Linux Benchmark structure but are intentionally
distribution-agnostic. To pin to a specific benchmark release (e.g. CIS Ubuntu
22.04 LTS v2.0.0 or CIS RHEL 9 v2.0.0), add or adjust controls in the matching
section file — the control `id`/`tag cis:` should carry the exact recommendation
number from that benchmark.
