# sabc_hardening (GENERATED — do not hand-edit)

This Puppet module is **generated from the unified SABC referential**
(`platform/seed/referentials/sabc_baseline/`) by
`backend/src/modules/profiles/artifact_generator.py` at seed time.

- One class per control (`sabc_hardening::<control_key>`), each branching
  internally on `$facts['os']['family']` (`Debian` / `RedHat`) so the same class
  covers Ubuntu/Debian/Mint and Alma/Rocky/RHEL/CentOS.
- Enforcement is the control's own **Configure** procedure, run idempotently:
  `exec { configure, unless => validate }` — an already-compliant node is a no-op.
- Every control's class exists regardless of CIS Level. Which classes a node
  applies is decided by that node's **tier** (`class { 'sabc_hardening': controls => [...] }`).

Regenerate: reseed the referential (bump the seed marker) or run the generator.
Controls whose Configure guidance is manual-only are listed in
`IMPLEMENTATION_PENDING.txt` and are intentionally NOT auto-enforced.
