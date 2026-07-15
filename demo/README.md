# CRICLO — Demo Kit

Scripts and a shot-by-shot filming plan for recording the demonstration video
(the source of the figures in the *Experimentation and Results* chapter).

Everything here runs **on the managed node** (Debian/Ubuntu family), as root,
and is **reversible**. Nothing touches the key aspects of the server — your SSH
session, sudo, networking, hostname/IP, and installed services are left intact.
Every file is backed up to `/var/backups/criclo-demo/<timestamp>/` before it is
changed, and `20_restore.sh` puts everything back.

> These scripts intentionally weaken a **demo** machine you own, to show the
> platform detecting and correcting the weakening. Do not run them on anything
> that matters, and delete the demo `mallory` account when you are done.

## Files

| Script | Run as | What it does |
|---|---|---|
| `00_prepare.sh` | root | Installs auditd + a watch rule (key `sabc-watch`) so a change can be attributed to a user; optionally creates a demo operator `mallory`. |
| `10_make_noncompliant.sh` | root | Applies a reproducible, reversible set of CIS-flagged weakenings to land the node near a **~49%** "before" score. Calibratable via `KNOB_*` flags. |
| `20_restore.sh` | root | Restores every backed-up file, removes the demo drop-ins, reloads services. |
| `30_inject_drift.sh` | the *attacker* via sudo | The on-camera "intrusion": sets `PermitRootLogin yes` on the watched `/etc/ssh/sshd_config`, attributed to whoever runs it. |
| `40_criclo_correct.sh` | root | The closed-loop **corrective**: comments the offending line (kept as proof, stamped with **who** + **why**), restores the compliant setting, reloads sshd, and **notifies the author why the change was blocked**. Honours `CRICLO_LOOP=on/off`. |
| `lib.sh` | — | Shared helpers (backup, safe sshd reload, auditd actor lookup, user notification). |

## Order of use

```bash
# One-time prep (attribution + demo user)
sudo ./00_prepare.sh

# Establish the ~49% baseline, then scan from the platform and calibrate
sudo ./10_make_noncompliant.sh
#   → run a scan in the UI; if not ~49%, flip a KNOB and re-run, e.g.:
#   sudo KNOB_SYSCTL=0 ./10_make_noncompliant.sh

# --- film enforcement: click Enforce in the UI; posture rises to ~88% ---

# --- film the closed loop (node enrolled, tier enforced, loop ON) ---
ssh mallory@<node>            # become the "author"
sudo /opt/criclo-demo/30_inject_drift.sh     # the intrusion
#   → detection event appears on the platform, attributed to mallory
sudo CRICLO_LOOP=on  /opt/criclo-demo/40_criclo_correct.sh   # correction + proof + notice

# --- film axis independence: same drift, loop OFF = evidence only ---
sudo CRICLO_LOOP=off /opt/criclo-demo/40_criclo_correct.sh

# Hand the box back clean
sudo ./20_restore.sh
```

## How this maps to the real platform

* **Detection** is real: the deployed detection agent watches `/etc/ssh/…` and
  forwards the change to the orchestrator, enriched with the author from auditd.
* **Decision** is real: whether a correction fires is governed by the node's
  closed-loop flag, exactly as `40_criclo_correct.sh` branches on `CRICLO_LOOP`.
* **Correction:** the platform's *default* corrective is a Puppet convergence
  that restores desired state. `40_criclo_correct.sh` is the demo's on-node
  corrective, chosen because it makes the **who / why / proof** tangible on
  camera (a commented line with attribution, and a message to the author). Use
  whichever you prefer for the shot — the platform-side evidence (the detection
  event carrying the actor) is identical either way.

See `FILMING.md` for the scene-by-scene plan and the voice-over script.
