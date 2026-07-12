"""
CIS Benchmark level per control (Level 1 vs Level 2) for the SABC Baseline.

The client's source referential left the "CIS Level" column blank for most rows,
which defaulted every control to Level 1 and made the Critical and Non-critical
tiers almost identical. This module assigns each control its REAL CIS level so
the tiers differentiate:

  * Non-critical  → Level 1 only  — the general-purpose server baseline that
    should hold on every host.
  * Critical      → Level 1 + Level 2 — plus the defence-in-depth measures that
    harden further, at a cost in functionality or that assume dedicated
    partitioning / auditing.

Mapping rule (applied by generate_seed.py): a CONTROL is Level 2 iff its Control
ID is listed in CIS_LEVEL_2; every other control is Level 1. Section rows carry
no level. This is authoritative — it overrides both the blanks and the few
inconsistent values in the source spreadsheet (e.g. cron.daily permissions and
the MOTD content check are Level 1 in the CIS Linux benchmarks, not Level 2).

The set is deliberately faithful, not inflated. In the CIS Ubuntu 22.04 / RHEL 9
benchmarks the overwhelming majority of these recommendations are Level 1; the
single largest Level-2 block — the auditd "System Accounting" chapter (~40 audit
rules) — is NOT part of this referential. If that chapter is imported later, its
recommendations should be added here as Level 2.
"""
from __future__ import annotations

__all__ = ["CIS_LEVEL_2", "level_for"]


# Control IDs that CIS designates Level 2. Everything else is Level 1.
CIS_LEVEL_2: set[str] = {
    # ── Dedicated partitions (Level 2) ───────────────────────────────────────
    # CIS marks separate partitions for /var, /var/tmp, /var/log,
    # /var/log/audit and /home as Level 2 (they need image-build-time layout);
    # /tmp and /dev/shm partitioning stay Level 1. The mount-option controls
    # below only take effect once that Level-2 partition exists, so they ride
    # with it into the Critical tier.
    "JR2.C.1.1.3.1", "JR2.C.1.1.3.2",                    # /var  — nodev, nosuid
    "JR2.C.1.1.4.1", "JR2.C.1.1.4.2", "JR2.C.1.1.4.3",  # /var/tmp — nodev, noexec, nosuid
    "JR2.C.1.1.5.1", "JR2.C.1.1.5.2", "JR2.C.1.1.5.3",  # /var/log — nodev, noexec, nosuid
    "JR2.C.1.1.6.1", "JR2.C.1.1.6.2", "JR2.C.1.1.6.3",  # /var/log/audit — nodev, noexec, nosuid
    "JR2.C.1.1.7.1", "JR2.C.1.1.7.2",                    # /home — nodev, nosuid

    # ── Bluetooth disabled (Level 2) ─────────────────────────────────────────
    # Functionality-affecting hardening — deferred from the general baseline.
    "JR2.C.3.1.2",

    # ── Audit-tool integrity (Level 2) ───────────────────────────────────────
    # "Ensure cryptographic mechanisms are used to protect the integrity of
    # audit tools" — part of the CIS auditd family, Level 2.
    "JR2.C.5.1.3.1",
}


def level_for(control_id: str) -> str:
    """Return the CIS level ('1' or '2') for a control id."""
    return "2" if control_id in CIS_LEVEL_2 else "1"
