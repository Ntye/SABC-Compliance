# SABC Linux Security Baseline (InSpec profile)

This is the InSpec profile the SABC compliance platform runs against every
managed node to produce structured compliance reports.

## How it runs

The platform invokes it **from the controller** over InSpec's agentless SSH
transport — no InSpec install is required on the managed nodes:

```bash
inspec exec sabc-linux-baseline \
  -t ssh://<user>@<host> \
  -i <ssh_key> --port <port> --sudo \
  --reporter json --chef-license accept-silent
```

The JSON output is parsed into `ComplianceReport` rows: every control becomes a
detail entry with its status (`pass`/`fail`/`skip`), an `impact` score, a derived
`severity` (high ≥ 0.7, medium ≥ 0.4, low > 0, info = 0) and the framework
references declared via `tag`.

## Control catalogue

| Group       | Controls                          | Theme                              |
|-------------|-----------------------------------|------------------------------------|
| `sshd-*`    | SSH daemon hardening              | CIS 5.2.x                          |
| `file-*`    | Critical file permissions         | CIS 5.2.1 / 6.1.x                  |
| `sysctl-*`  | Kernel network/memory hardening   | CIS 1.5.x / 3.x                    |
| `svc-*`     | Auditing, firewall, services      | CIS 2.x / 3.5 / 4.1                |
| `auth-*`    | Password policy                   | CIS 5.4.1.x                        |

Every control is tagged with `cis`, and where applicable `iso27001` and
`pci_dss`, so reports can be filtered by framework.
