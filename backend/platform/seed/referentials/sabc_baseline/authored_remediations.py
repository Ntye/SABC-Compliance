"""
Authored per-control remediations for the SABC Baseline referential.

The source spreadsheet carries the CIS guidance verbatim; for ~35 controls that
guidance is CONTENT TO WRITE (pwquality values, sudoers defaults, journald
settings, umask, TMOUT …) or an audit whose polarity/robustness doesn't survive
mechanical extraction ("verify no results are returned" greps, checks that
explode when the underlying package is absent). Those controls scanned wrong or
stayed implementation-pending.

This module replaces their Debian-family Validate/Configure cells (and, where
the families genuinely diverge, the Red Hat cells) with hand-written idempotent
scripts. ``generate_seed.py`` applies these AFTER loading the spreadsheet and
BEFORE the Red Hat derivation, so regenerating the committed CSV never loses
them and the client's xlsx stays untouched.

Script contract (enforced by tests/test_authored_remediations.py):

  * every script starts with ``#!/bin/bash`` — that routes it verbatim through
    ``extract_shell`` (no prompt/config-content heuristics apply);
  * Validate exits 0 = compliant, 1 = non-compliant, 101 = NOT APPLICABLE on
    this node (prerequisite package/service absent — the scan reports a skip,
    enforcement does nothing);
  * Configure is idempotent and safe to re-run; when the control does not apply
    it exits 0 without touching anything;
  * anything that edits sudoers goes through ``visudo -cf`` and rolls back on a
    syntax error; anything that edits sshd_config runs ``sshd -t`` before
    reloading — a bad remediation must never lock the platform out.

Deliberately NOT remediated here (policy, not tooling):
  * JR2.C.1.3.1 bootloader password — requires an organisation-chosen secret;
  * JR2.C.1.1.2.x–1.1.7.x separate partitions — impossible to create on a
    running single-volume system (image-build-time work or a formal waiver).
"""
from __future__ import annotations

import textwrap

__all__ = ["REMEDIATIONS"]


def _cell(prose: str, script: str) -> str:
    """One referential cell: a prose line + a fenced bash script block."""
    body = textwrap.dedent(script).strip("\n")
    return f"{prose}\n\n```bash\n#!/bin/bash\n{body}\n```"


# Shared shell fragment: set (or update) `key = value` in a pwquality-style
# conf file, uncommenting an existing line when present.
_SET_KV = r"""
set_kv() {
  k="$1"; v="$2"; f="$3"
  if grep -Eq "^[[:space:]]*#?[[:space:]]*$k[[:space:]]*=" "$f" 2>/dev/null; then
    sed -ri "s|^[[:space:]]*#?[[:space:]]*($k)[[:space:]]*=.*|\1 = $v|" "$f"
  else
    printf '%s = %s\n' "$k" "$v" >> "$f"
  fi
}
"""


REMEDIATIONS: dict[str, dict[str, str]] = {

    # ── 1.1.8 /dev/shm mount options (the one fixable "partition" control) ────
    "JR2.C.1.1.8.1": {
        "validate_debian": _cell(
            "Verify the live /dev/shm mount carries the nodev option "
            "(not applicable when /dev/shm is not a mount point).",
            r"""
            findmnt -kn /dev/shm >/dev/null 2>&1 || exit 101
            findmnt -kn /dev/shm | grep -qw nodev && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Pin /dev/shm in fstab with nodev,nosuid,noexec and remount.",
            r"""
            findmnt -kn /dev/shm >/dev/null 2>&1 || exit 0
            if grep -Eq '^[[:space:]]*tmpfs[[:space:]]+/dev/shm[[:space:]]' /etc/fstab; then
              sed -ri 's|^([[:space:]]*tmpfs[[:space:]]+/dev/shm[[:space:]]+tmpfs[[:space:]]+)[^[:space:]]+|\1defaults,rw,nosuid,nodev,noexec,relatime|' /etc/fstab
            else
              printf 'tmpfs /dev/shm tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0\n' >> /etc/fstab
            fi
            mount -o remount /dev/shm 2>/dev/null || true
            exit 0
            """),
    },
    "JR2.C.1.1.8.3": {
        "validate_debian": _cell(
            "Verify the live /dev/shm mount carries the nosuid option "
            "(not applicable when /dev/shm is not a mount point).",
            r"""
            findmnt -kn /dev/shm >/dev/null 2>&1 || exit 101
            findmnt -kn /dev/shm | grep -qw nosuid && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Pin /dev/shm in fstab with nodev,nosuid,noexec and remount.",
            r"""
            findmnt -kn /dev/shm >/dev/null 2>&1 || exit 0
            if grep -Eq '^[[:space:]]*tmpfs[[:space:]]+/dev/shm[[:space:]]' /etc/fstab; then
              sed -ri 's|^([[:space:]]*tmpfs[[:space:]]+/dev/shm[[:space:]]+tmpfs[[:space:]]+)[^[:space:]]+|\1defaults,rw,nosuid,nodev,noexec,relatime|' /etc/fstab
            else
              printf 'tmpfs /dev/shm tmpfs defaults,rw,nosuid,nodev,noexec,relatime 0 0\n' >> /etc/fstab
            fi
            mount -o remount /dev/shm 2>/dev/null || true
            exit 0
            """),
    },

    # ── 1.2.2 AIDE scheduled check ─────────────────────────────────────────────
    # Self-branching (Debian aide.wrapper/timer vs RHEL /usr/sbin/aide) so the
    # mechanical Red Hat derivation keeps it correct as-is.
    "JR2.C.1.2.2": {
        "validate_debian": _cell(
            "Verify a periodic AIDE integrity check is scheduled (cron entry "
            "or the distribution's aide check timer).",
            r"""
            crontab -u root -l 2>/dev/null | grep -Eq '(^|/)(aide|aide\.wrapper)\b' && exit 0
            grep -Ersq '(^|/)(aide|aide\.wrapper)\b' /etc/cron.d /etc/cron.daily 2>/dev/null && exit 0
            systemctl is-enabled dailyaidecheck.timer >/dev/null 2>&1 && exit 0
            systemctl is-enabled aidecheck.timer >/dev/null 2>&1 && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Schedule the AIDE check: enable the distribution timer when it "
            "exists, otherwise install a root cron entry.",
            r"""
            if systemctl list-unit-files 2>/dev/null | grep -q '^dailyaidecheck\.timer'; then
              systemctl unmask dailyaidecheck.timer >/dev/null 2>&1
              systemctl enable --now dailyaidecheck.timer >/dev/null 2>&1 && exit 0
            fi
            if [ -x /usr/bin/aide.wrapper ]; then
              printf '0 5 * * * root /usr/bin/aide.wrapper --config /etc/aide/aide.conf --check\n' > /etc/cron.d/aide-check
            else
              printf '0 5 * * * root /usr/sbin/aide --check\n' > /etc/cron.d/aide-check
            fi
            chmod 644 /etc/cron.d/aide-check
            exit 0
            """),
    },

    # ── 1.4.5 core dumps ───────────────────────────────────────────────────────
    "JR2.C.1.4.5": {
        "validate_debian": _cell(
            "Verify core dumps are restricted: hard limit 0, fs.suid_dumpable=0 "
            "live and persisted (systemd-coredump storage disabled when present).",
            r"""
            grep -Ersq '^[[:space:]]*\*[[:space:]]+hard[[:space:]]+core[[:space:]]+0\b' /etc/security/limits.conf /etc/security/limits.d 2>/dev/null || exit 1
            [ "$(sysctl -n fs.suid_dumpable 2>/dev/null)" = "0" ] || exit 1
            grep -Ersq '^[[:space:]]*fs\.suid_dumpable[[:space:]]*=[[:space:]]*0\b' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
            if [ -e /etc/systemd/coredump.conf ] || [ -d /etc/systemd/coredump.conf.d ]; then
              grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/coredump.conf /etc/systemd/coredump.conf.d/*.conf 2>/dev/null | tail -1 | grep -q 'none' || exit 1
            fi
            exit 0
            """),
        "configure_debian": _cell(
            "Restrict core dumps via limits.d, sysctl.d and (when present) a "
            "systemd-coredump drop-in.",
            r"""
            printf '* hard core 0\n' > /etc/security/limits.d/50-sabc-core.conf
            printf 'fs.suid_dumpable = 0\n' > /etc/sysctl.d/60-sabc-coredump.conf
            sysctl -w fs.suid_dumpable=0 >/dev/null
            if [ -e /etc/systemd/coredump.conf ] || [ -d /etc/systemd/coredump.conf.d ]; then
              mkdir -p /etc/systemd/coredump.conf.d
              printf '[Coredump]\nStorage=none\nProcessSizeMax=0\n' > /etc/systemd/coredump.conf.d/60-sabc.conf
            fi
            exit 0
            """),
    },

    # ── 1.5.1 AppArmor installed (Debian; Red Hat keeps its SELinux override) ──
    "JR2.C.1.5.1": {
        "validate_debian": _cell(
            "Verify BOTH apparmor and apparmor-utils are installed.",
            r"""
            dpkg-query -W apparmor >/dev/null 2>&1 || exit 1
            dpkg-query -W apparmor-utils >/dev/null 2>&1 || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Install AppArmor and its utilities.",
            r"""
            DEBIAN_FRONTEND=noninteractive apt-get -y install apparmor apparmor-utils >/dev/null
            exit 0
            """),
    },

    # ── 1.6.1 message of the day ───────────────────────────────────────────────
    "JR2.C.1.6.1": {
        "validate_debian": _cell(
            "Verify /etc/motd (when present) contains no escape sequences or "
            "OS-identity references — an absent motd is compliant.",
            r"""
            [ -e /etc/motd ] || exit 0
            os_id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
            grep -Eqis "(\\\\v|\\\\r|\\\\m|\\\\s|$os_id)" /etc/motd && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Strip escape sequences and OS-identity references from /etc/motd.",
            r"""
            [ -e /etc/motd ] || exit 0
            os_id=$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
            sed -ri "s/\\\\[mrsv]//g" /etc/motd
            [ -n "$os_id" ] && sed -ri "s/$os_id//gI" /etc/motd
            exit 0
            """),
    },
    "JR2.C.1.6.4": {
        "validate_debian": _cell(
            "Verify permissions on /etc/motd are 644 root:root (an absent motd "
            "is compliant).",
            r"""
            [ -e /etc/motd ] || exit 0
            [ "$(stat -c '%a %U %G' /etc/motd)" = "644 root root" ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set /etc/motd to 644 root:root when the file exists.",
            r"""
            [ -e /etc/motd ] || exit 0
            chown root:root /etc/motd
            chmod 644 /etc/motd
            exit 0
            """),
    },

    # ── 1.7.9 XDMCP (GDM) — not applicable on a headless server ────────────────
    "JR2.C.1.7.9": {
        "validate_debian": _cell(
            "Verify XDMCP is not enabled in GDM (not applicable when GDM is "
            "not installed).",
            r"""
            dpkg-query -W gdm3 >/dev/null 2>&1 || exit 101
            grep -Eqsi '^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true' /etc/gdm3/custom.conf /etc/gdm/custom.conf 2>/dev/null && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Disable XDMCP in the GDM configuration when GDM is installed.",
            r"""
            dpkg-query -W gdm3 >/dev/null 2>&1 || exit 0
            for f in /etc/gdm3/custom.conf /etc/gdm/custom.conf; do
              [ -e "$f" ] && sed -ri 's/^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true/Enable=false/I' "$f"
            done
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify XDMCP is not enabled in GDM (not applicable when GDM is "
            "not installed).",
            r"""
            rpm -q gdm >/dev/null 2>&1 || exit 101
            grep -Eqsi '^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true' /etc/gdm/custom.conf 2>/dev/null && exit 1
            exit 0
            """),
        "configure_redhat": _cell(
            "Disable XDMCP in the GDM configuration when GDM is installed.",
            r"""
            rpm -q gdm >/dev/null 2>&1 || exit 0
            [ -e /etc/gdm/custom.conf ] && sed -ri 's/^[[:space:]]*Enable[[:space:]]*=[[:space:]]*true/Enable=false/I' /etc/gdm/custom.conf
            exit 0
            """),
    },

    # ── 2.1 time synchronisation (single-daemon sections are alternatives) ────
    "JR2.C.2.1.3.1": {
        "validate_debian": _cell(
            "Verify systemd-timesyncd is configured with a timeserver — not "
            "applicable when timesyncd is not the enabled sync daemon (e.g. "
            "chrony hosts).",
            r"""
            systemctl is-enabled systemd-timesyncd 2>/dev/null | grep -q '^enabled' || exit 101
            grep -Ersq '^[[:space:]]*(NTP|FallbackNTP)=[^[:space:]]' /etc/systemd/timesyncd.conf /etc/systemd/timesyncd.conf.d 2>/dev/null && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Point systemd-timesyncd at authorized pool servers (drop-in).",
            r"""
            systemctl is-enabled systemd-timesyncd 2>/dev/null | grep -q '^enabled' || exit 0
            mkdir -p /etc/systemd/timesyncd.conf.d
            printf '[Time]\nNTP=0.pool.ntp.org 1.pool.ntp.org\nFallbackNTP=2.pool.ntp.org 3.pool.ntp.org\n' > /etc/systemd/timesyncd.conf.d/60-sabc.conf
            systemctl try-restart systemd-timesyncd >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.2.1.4.1": {
        "validate_debian": _cell(
            "Verify ntp restricts the default association — not applicable "
            "when the ntp daemon is not installed (chrony/timesyncd hosts).",
            r"""
            dpkg-query -W ntp >/dev/null 2>&1 || dpkg-query -W ntpsec >/dev/null 2>&1 || exit 101
            f=/etc/ntpsec/ntp.conf; [ -e "$f" ] || f=/etc/ntp.conf
            [ -e "$f" ] || exit 1
            for v in 4 6; do
              line=$(grep -Es "^[[:space:]]*restrict[[:space:]]+(-$v[[:space:]]+)?default\b" "$f" | head -1)
              [ -n "$line" ] || exit 1
              for opt in kod nomodify notrap nopeer noquery; do
                printf '%s' "$line" | grep -qw "$opt" || exit 1
              done
            done
            exit 0
            """),
        "configure_debian": _cell(
            "Apply the CIS default restrictions to the ntp configuration.",
            r"""
            dpkg-query -W ntp >/dev/null 2>&1 || dpkg-query -W ntpsec >/dev/null 2>&1 || exit 0
            f=/etc/ntpsec/ntp.conf; [ -e "$f" ] || f=/etc/ntp.conf
            [ -e "$f" ] || exit 0
            grep -Eq '^[[:space:]]*restrict[[:space:]]+(-4[[:space:]]+)?default' "$f" \
              && sed -ri 's|^[[:space:]]*restrict[[:space:]]+(-4[[:space:]]+)?default.*|restrict -4 default kod nomodify notrap nopeer noquery|' "$f" \
              || printf 'restrict -4 default kod nomodify notrap nopeer noquery\n' >> "$f"
            grep -Eq '^[[:space:]]*restrict[[:space:]]+-6[[:space:]]+default' "$f" \
              && sed -ri 's|^[[:space:]]*restrict[[:space:]]+-6[[:space:]]+default.*|restrict -6 default kod nomodify notrap nopeer noquery|' "$f" \
              || printf 'restrict -6 default kod nomodify notrap nopeer noquery\n' >> "$f"
            systemctl try-restart ntp >/dev/null 2>&1 || systemctl try-restart ntpsec >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.2.1.4.3": {
        "validate_debian": _cell(
            "Verify the ntp daemon is enabled and running — not applicable "
            "when ntp is not installed (chrony/timesyncd hosts).",
            r"""
            dpkg-query -W ntp >/dev/null 2>&1 || dpkg-query -W ntpsec >/dev/null 2>&1 || exit 101
            for u in ntp ntpsec; do
              if systemctl is-enabled "$u" 2>/dev/null | grep -q '^enabled'; then
                systemctl is-active "$u" 2>/dev/null | grep -qx active && exit 0
              fi
            done
            exit 1
            """),
        "configure_debian": _cell(
            "Enable and start the installed ntp daemon.",
            r"""
            if dpkg-query -W ntpsec >/dev/null 2>&1; then u=ntpsec
            elif dpkg-query -W ntp >/dev/null 2>&1; then u=ntp
            else exit 0; fi
            systemctl unmask "$u" >/dev/null 2>&1
            systemctl enable --now "$u" >/dev/null 2>&1
            exit 0
            """),
    },

    # ── 2.2.16 rsync not installed or masked ───────────────────────────────────
    "JR2.C.2.2.16": {
        "validate_debian": _cell(
            "Verify the rsync service is absent or masked (an uninstalled "
            "rsync is compliant).",
            r"""
            dpkg-query -W rsync >/dev/null 2>&1 || exit 0
            systemctl list-unit-files 2>/dev/null | grep -q '^rsync\.service' || exit 0
            [ "$(systemctl is-enabled rsync 2>/dev/null)" = "masked" ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Stop and mask the rsync service when it exists.",
            r"""
            systemctl list-unit-files 2>/dev/null | grep -q '^rsync\.service' || exit 0
            systemctl stop rsync >/dev/null 2>&1
            systemctl mask rsync >/dev/null 2>&1
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify the rsync daemon is absent or masked (an uninstalled "
            "rsync-daemon is compliant).",
            r"""
            rpm -q rsync-daemon >/dev/null 2>&1 || rpm -q rsync >/dev/null 2>&1 || exit 0
            systemctl list-unit-files 2>/dev/null | grep -q '^rsyncd\.service' || exit 0
            [ "$(systemctl is-enabled rsyncd 2>/dev/null)" = "masked" ] && exit 0
            exit 1
            """),
        "configure_redhat": _cell(
            "Stop and mask the rsyncd service when it exists.",
            r"""
            systemctl list-unit-files 2>/dev/null | grep -q '^rsyncd\.service' || exit 0
            systemctl stop rsyncd >/dev/null 2>&1
            systemctl mask rsyncd >/dev/null 2>&1
            exit 0
            """),
    },

    # ── 2.3.4 telnet client removed ────────────────────────────────────────────
    "JR2.C.2.3.4": {
        "configure_debian": _cell(
            "Purge the telnet client packages when installed.",
            r"""
            for p in telnet inetutils-telnet; do
              dpkg-query -W "$p" >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get -y purge "$p" >/dev/null
            done
            exit 0
            """),
    },

    # ── 3.1.2 bluetooth disabled ───────────────────────────────────────────────
    "JR2.C.3.1.2": {
        "validate_debian": _cell(
            "Verify bluetooth is disabled: bluez absent, or the bluetooth "
            "service neither active nor enabled.",
            r"""
            dpkg-query -W bluez >/dev/null 2>&1 || exit 0
            systemctl is-active bluetooth 2>/dev/null | grep -qx active && exit 1
            systemctl is-enabled bluetooth 2>/dev/null | grep -q '^enabled' && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Stop and mask the bluetooth service when the unit exists.",
            r"""
            systemctl list-unit-files 2>/dev/null | grep -q '^bluetooth\.service' || exit 0
            systemctl stop bluetooth >/dev/null 2>&1
            systemctl mask bluetooth >/dev/null 2>&1
            exit 0
            """),
    },

    # ── 3.3.4 suspicious packets logged ────────────────────────────────────────
    "JR2.C.3.3.4": {
        "validate_debian": _cell(
            "Verify log_martians is 1 live AND persisted for all/default.",
            r"""
            [ "$(sysctl -n net.ipv4.conf.all.log_martians 2>/dev/null)" = "1" ] || exit 1
            [ "$(sysctl -n net.ipv4.conf.default.log_martians 2>/dev/null)" = "1" ] || exit 1
            grep -Ersq '^[[:space:]]*net\.ipv4\.conf\.all\.log_martians[[:space:]]*=[[:space:]]*1' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
            grep -Ersq '^[[:space:]]*net\.ipv4\.conf\.default\.log_martians[[:space:]]*=[[:space:]]*1' /etc/sysctl.conf /etc/sysctl.d 2>/dev/null || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Enable martian-packet logging live and persistently.",
            r"""
            printf 'net.ipv4.conf.all.log_martians = 1\nnet.ipv4.conf.default.log_martians = 1\n' > /etc/sysctl.d/60-sabc-netlog.conf
            sysctl -w net.ipv4.conf.all.log_martians=1 >/dev/null
            sysctl -w net.ipv4.conf.default.log_martians=1 >/dev/null
            sysctl -w net.ipv4.route.flush=1 >/dev/null
            exit 0
            """),
    },

    # ── 3.4 firewall — the three sections are ALTERNATIVES (CIS: choose one). ──
    # ufw section applies when ufw is installed; the nftables/iptables sections
    # are not applicable while ufw is the active firewall (ufw drives both
    # backends itself), and vice-versa on Red Hat with firewalld.
    "JR2.C.3.4.1.2": {
        "validate_debian": _cell(
            "Verify iptables-persistent is not installed alongside ufw (not "
            "applicable when ufw is not installed).",
            r"""
            dpkg-query -W ufw >/dev/null 2>&1 || exit 101
            dpkg-query -W iptables-persistent >/dev/null 2>&1 && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Purge iptables-persistent when ufw is the firewall.",
            r"""
            dpkg-query -W ufw >/dev/null 2>&1 || exit 0
            dpkg-query -W iptables-persistent >/dev/null 2>&1 || exit 0
            DEBIAN_FRONTEND=noninteractive apt-get -y purge iptables-persistent >/dev/null
            exit 0
            """),
        "validate_redhat": _cell(
            "ufw is not used on the Red Hat family (firewalld is the frontend) "
            "— this control is not applicable there.",
            r"""
            exit 101
            """),
        "configure_redhat": _cell(
            "ufw is not used on the Red Hat family — nothing to configure.",
            r"""
            exit 0
            """),
    },
    "JR2.C.3.4.1.6": {
        "validate_debian": _cell(
            "Verify ufw default-deny policy (incoming, outgoing, routed) — not "
            "applicable when ufw is not installed.",
            r"""
            dpkg-query -W ufw >/dev/null 2>&1 || exit 101
            ufw status verbose 2>/dev/null | grep -q 'Status: active' || exit 1
            ufw status verbose 2>/dev/null | grep -Eq 'Default: deny \(incoming\), deny \(outgoing\), (deny|disabled) \(routed\)' && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set ufw default deny — after allowing SSH in and the platform's "
            "outbound dependencies (DNS/HTTP/HTTPS/NTP) so remediation cannot "
            "cut the node off.",
            r"""
            dpkg-query -W ufw >/dev/null 2>&1 || exit 0
            ufw status 2>/dev/null | grep -q 'Status: active' || exit 0
            ufw allow in 22/tcp >/dev/null 2>&1
            ufw allow out 53 >/dev/null 2>&1
            ufw allow out 80/tcp >/dev/null 2>&1
            ufw allow out 443/tcp >/dev/null 2>&1
            ufw allow out 123/udp >/dev/null 2>&1
            ufw default deny incoming >/dev/null 2>&1
            ufw default deny outgoing >/dev/null 2>&1
            ufw default deny routed >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.3.4.2.4": {
        "validate_debian": _cell(
            "Verify nftables base chains exist — not applicable while ufw is "
            "the active firewall or nftables is not installed.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            dpkg-query -W nftables >/dev/null 2>&1 || exit 101
            r=$(nft list ruleset 2>/dev/null) || exit 1
            printf '%s' "$r" | grep -q 'hook input' || exit 1
            printf '%s' "$r" | grep -q 'hook forward' || exit 1
            printf '%s' "$r" | grep -q 'hook output' || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Create the inet filter table and base chains (policy accept — the "
            "default-deny control flips policy only after accept rules exist).",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            dpkg-query -W nftables >/dev/null 2>&1 || exit 0
            nft list table inet filter >/dev/null 2>&1 || nft create table inet filter
            nft list chain inet filter input >/dev/null 2>&1 || nft create chain inet filter input '{ type filter hook input priority 0 ; policy accept ; }'
            nft list chain inet filter forward >/dev/null 2>&1 || nft create chain inet filter forward '{ type filter hook forward priority 0 ; policy accept ; }'
            nft list chain inet filter output >/dev/null 2>&1 || nft create chain inet filter output '{ type filter hook output priority 0 ; policy accept ; }'
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify nftables base chains exist — not applicable while "
            "firewalld is the active firewall or nftables is not installed.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            rpm -q nftables >/dev/null 2>&1 || exit 101
            r=$(nft list ruleset 2>/dev/null) || exit 1
            printf '%s' "$r" | grep -q 'hook input' || exit 1
            printf '%s' "$r" | grep -q 'hook forward' || exit 1
            printf '%s' "$r" | grep -q 'hook output' || exit 1
            exit 0
            """),
        "configure_redhat": _cell(
            "Create the inet filter table and base chains (policy accept — the "
            "default-deny control flips policy only after accept rules exist).",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            rpm -q nftables >/dev/null 2>&1 || exit 0
            nft list table inet filter >/dev/null 2>&1 || nft create table inet filter
            nft list chain inet filter input >/dev/null 2>&1 || nft create chain inet filter input '{ type filter hook input priority 0 ; policy accept ; }'
            nft list chain inet filter forward >/dev/null 2>&1 || nft create chain inet filter forward '{ type filter hook forward priority 0 ; policy accept ; }'
            nft list chain inet filter output >/dev/null 2>&1 || nft create chain inet filter output '{ type filter hook output priority 0 ; policy accept ; }'
            exit 0
            """),
    },
    "JR2.C.3.4.2.5": {
        "validate_debian": _cell(
            "Verify nftables loopback traffic is configured — not applicable "
            "while ufw is the active firewall or nftables is not installed.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            dpkg-query -W nftables >/dev/null 2>&1 || exit 101
            r=$(nft list ruleset 2>/dev/null) || exit 1
            printf '%s' "$r" | grep -q 'iif "lo" accept' || exit 1
            printf '%s' "$r" | grep -Eq 'ip saddr 127\.0\.0\.0/8.*drop' || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Add the loopback accept and spoofed-loopback drop rules.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            dpkg-query -W nftables >/dev/null 2>&1 || exit 0
            nft list chain inet filter input >/dev/null 2>&1 || exit 0
            nft list chain inet filter input | grep -q 'iif "lo" accept' || nft add rule inet filter input iif lo accept
            nft list chain inet filter input | grep -Eq 'ip saddr 127\.0\.0\.0/8.*drop' || nft add rule inet filter input ip saddr 127.0.0.0/8 counter drop
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify nftables loopback traffic is configured — not applicable "
            "while firewalld is the active firewall or nftables is not installed.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            rpm -q nftables >/dev/null 2>&1 || exit 101
            r=$(nft list ruleset 2>/dev/null) || exit 1
            printf '%s' "$r" | grep -q 'iif "lo" accept' || exit 1
            printf '%s' "$r" | grep -Eq 'ip saddr 127\.0\.0\.0/8.*drop' || exit 1
            exit 0
            """),
        "configure_redhat": _cell(
            "Add the loopback accept and spoofed-loopback drop rules.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            rpm -q nftables >/dev/null 2>&1 || exit 0
            nft list chain inet filter input >/dev/null 2>&1 || exit 0
            nft list chain inet filter input | grep -q 'iif "lo" accept' || nft add rule inet filter input iif lo accept
            nft list chain inet filter input | grep -Eq 'ip saddr 127\.0\.0\.0/8.*drop' || nft add rule inet filter input ip saddr 127.0.0.0/8 counter drop
            exit 0
            """),
    },
    "JR2.C.3.4.2.6": {
        "validate_debian": _cell(
            "Verify every nftables base chain uses policy drop — not "
            "applicable while ufw is the active firewall or nftables is not "
            "installed.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            dpkg-query -W nftables >/dev/null 2>&1 || exit 101
            r=$(nft list ruleset 2>/dev/null) || exit 1
            printf '%s' "$r" | grep -q 'hook input' || exit 1
            n=$(printf '%s' "$r" | grep -cE 'hook (input|forward|output)')
            d=$(printf '%s' "$r" | grep -E 'hook (input|forward|output)' | grep -c 'policy drop')
            [ "$n" -gt 0 ] && [ "$n" -eq "$d" ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Flip base-chain policies to drop — only after ensuring loopback, "
            "established-traffic and SSH accept rules exist (lockout guard).",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            dpkg-query -W nftables >/dev/null 2>&1 || exit 0
            nft list chain inet filter input >/dev/null 2>&1 || exit 0
            nft list chain inet filter input | grep -q 'iif "lo" accept' || nft add rule inet filter input iif lo accept
            nft list chain inet filter input | grep -q 'ct state established,related accept' || nft add rule inet filter input ct state established,related accept
            nft list chain inet filter input | grep -q 'tcp dport 22 accept' || nft add rule inet filter input tcp dport 22 accept
            nft list chain inet filter output | grep -q 'ct state established,related accept' || nft add rule inet filter output ct state established,related accept
            for ch in input forward output; do
              nft chain inet filter "$ch" '{ policy drop ; }'
            done
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify every nftables base chain uses policy drop — not "
            "applicable while firewalld is the active firewall or nftables is "
            "not installed.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            rpm -q nftables >/dev/null 2>&1 || exit 101
            r=$(nft list ruleset 2>/dev/null) || exit 1
            printf '%s' "$r" | grep -q 'hook input' || exit 1
            n=$(printf '%s' "$r" | grep -cE 'hook (input|forward|output)')
            d=$(printf '%s' "$r" | grep -E 'hook (input|forward|output)' | grep -c 'policy drop')
            [ "$n" -gt 0 ] && [ "$n" -eq "$d" ] && exit 0
            exit 1
            """),
        "configure_redhat": _cell(
            "Flip base-chain policies to drop — only after ensuring loopback, "
            "established-traffic and SSH accept rules exist (lockout guard).",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            rpm -q nftables >/dev/null 2>&1 || exit 0
            nft list chain inet filter input >/dev/null 2>&1 || exit 0
            nft list chain inet filter input | grep -q 'iif "lo" accept' || nft add rule inet filter input iif lo accept
            nft list chain inet filter input | grep -q 'ct state established,related accept' || nft add rule inet filter input ct state established,related accept
            nft list chain inet filter input | grep -q 'tcp dport 22 accept' || nft add rule inet filter input tcp dport 22 accept
            nft list chain inet filter output | grep -q 'ct state established,related accept' || nft add rule inet filter output ct state established,related accept
            for ch in input forward output; do
              nft chain inet filter "$ch" '{ policy drop ; }'
            done
            exit 0
            """),
    },
    "JR2.C.3.4.2.8": {
        "validate_debian": _cell(
            "Verify nftables rules are persisted via /etc/nftables.conf — not "
            "applicable while ufw is the active firewall or nftables is not "
            "installed.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            dpkg-query -W nftables >/dev/null 2>&1 || exit 101
            grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables\.d/sabc\.nft"' /etc/nftables.conf && [ -s /etc/nftables.d/sabc.nft ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Persist the live ruleset to /etc/nftables.d/sabc.nft and include "
            "it from /etc/nftables.conf.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            dpkg-query -W nftables >/dev/null 2>&1 || exit 0
            mkdir -p /etc/nftables.d
            nft list ruleset > /etc/nftables.d/sabc.nft 2>/dev/null || exit 0
            grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables\.d/sabc\.nft"' /etc/nftables.conf || printf 'include "/etc/nftables.d/sabc.nft"\n' >> /etc/nftables.conf
            systemctl enable nftables >/dev/null 2>&1
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify nftables rules are persisted — not applicable while "
            "firewalld is the active firewall or nftables is not installed.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            rpm -q nftables >/dev/null 2>&1 || exit 101
            grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables/sabc\.nft"' /etc/sysconfig/nftables.conf && [ -s /etc/nftables/sabc.nft ] && exit 0
            exit 1
            """),
        "configure_redhat": _cell(
            "Persist the live ruleset to /etc/nftables/sabc.nft and include it "
            "from /etc/sysconfig/nftables.conf.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            rpm -q nftables >/dev/null 2>&1 || exit 0
            mkdir -p /etc/nftables
            nft list ruleset > /etc/nftables/sabc.nft 2>/dev/null || exit 0
            grep -Eqs '^[[:space:]]*include[[:space:]]+"/etc/nftables/sabc\.nft"' /etc/sysconfig/nftables.conf || printf 'include "/etc/nftables/sabc.nft"\n' >> /etc/sysconfig/nftables.conf
            systemctl enable nftables >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.3.4.3.1.2": {
        "validate_debian": _cell(
            "Verify nftables is not installed when iptables is the chosen "
            "firewall — not applicable while ufw or the nftables service is "
            "the active firewall.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
            dpkg-query -W nftables >/dev/null 2>&1 && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Remove nftables only when iptables is the chosen firewall.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
            dpkg-query -W nftables >/dev/null 2>&1 || exit 0
            DEBIAN_FRONTEND=noninteractive apt-get -y purge nftables >/dev/null
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify nftables is not installed when iptables is the chosen "
            "firewall — not applicable while firewalld or the nftables "
            "service is the active firewall.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
            rpm -q nftables >/dev/null 2>&1 && exit 1
            exit 0
            """),
        "configure_redhat": _cell(
            "Remove nftables only when iptables is the chosen firewall.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
            rpm -q nftables >/dev/null 2>&1 || exit 0
            dnf remove -y nftables >/dev/null
            exit 0
            """),
    },
    "JR2.C.3.4.3.2.2": {
        "validate_debian": _cell(
            "Verify iptables loopback rules — not applicable while ufw or the "
            "nftables service is the active firewall.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
            command -v iptables >/dev/null 2>&1 || exit 1
            iptables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || exit 1
            iptables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || exit 1
            iptables -C INPUT -s 127.0.0.0/8 -j DROP >/dev/null 2>&1 || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Install the iptables loopback rules when iptables is the chosen "
            "firewall.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
            command -v iptables >/dev/null 2>&1 || exit 0
            iptables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || iptables -A INPUT -i lo -j ACCEPT
            iptables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || iptables -A OUTPUT -o lo -j ACCEPT
            iptables -C INPUT -s 127.0.0.0/8 -j DROP >/dev/null 2>&1 || iptables -A INPUT -s 127.0.0.0/8 -j DROP
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify iptables loopback rules — not applicable while firewalld "
            "or the nftables service is the active firewall.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
            command -v iptables >/dev/null 2>&1 || exit 1
            iptables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || exit 1
            iptables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || exit 1
            iptables -C INPUT -s 127.0.0.0/8 -j DROP >/dev/null 2>&1 || exit 1
            exit 0
            """),
        "configure_redhat": _cell(
            "Install the iptables loopback rules when iptables is the chosen "
            "firewall.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
            command -v iptables >/dev/null 2>&1 || exit 0
            iptables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || iptables -A INPUT -i lo -j ACCEPT
            iptables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || iptables -A OUTPUT -o lo -j ACCEPT
            iptables -C INPUT -s 127.0.0.0/8 -j DROP >/dev/null 2>&1 || iptables -A INPUT -s 127.0.0.0/8 -j DROP
            exit 0
            """),
    },
    "JR2.C.3.4.3.3.2": {
        "validate_debian": _cell(
            "Verify ip6tables loopback rules — not applicable while ufw or the "
            "nftables service is the active firewall.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 101
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
            command -v ip6tables >/dev/null 2>&1 || exit 1
            ip6tables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || exit 1
            ip6tables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || exit 1
            ip6tables -C INPUT -s ::1 -j DROP >/dev/null 2>&1 || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Install the ip6tables loopback rules when iptables is the chosen "
            "firewall.",
            r"""
            systemctl is-active ufw 2>/dev/null | grep -qx active && exit 0
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
            command -v ip6tables >/dev/null 2>&1 || exit 0
            ip6tables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || ip6tables -A INPUT -i lo -j ACCEPT
            ip6tables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || ip6tables -A OUTPUT -o lo -j ACCEPT
            ip6tables -C INPUT -s ::1 -j DROP >/dev/null 2>&1 || ip6tables -A INPUT -s ::1 -j DROP
            exit 0
            """),
        "validate_redhat": _cell(
            "Verify ip6tables loopback rules — not applicable while firewalld "
            "or the nftables service is the active firewall.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 101
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 101
            command -v ip6tables >/dev/null 2>&1 || exit 1
            ip6tables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || exit 1
            ip6tables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || exit 1
            ip6tables -C INPUT -s ::1 -j DROP >/dev/null 2>&1 || exit 1
            exit 0
            """),
        "configure_redhat": _cell(
            "Install the ip6tables loopback rules when iptables is the chosen "
            "firewall.",
            r"""
            systemctl is-active firewalld 2>/dev/null | grep -qx active && exit 0
            systemctl is-enabled nftables 2>/dev/null | grep -q '^enabled' && exit 0
            command -v ip6tables >/dev/null 2>&1 || exit 0
            ip6tables -C INPUT -i lo -j ACCEPT >/dev/null 2>&1 || ip6tables -A INPUT -i lo -j ACCEPT
            ip6tables -C OUTPUT -o lo -j ACCEPT >/dev/null 2>&1 || ip6tables -A OUTPUT -o lo -j ACCEPT
            ip6tables -C INPUT -s ::1 -j DROP >/dev/null 2>&1 || ip6tables -A INPUT -s ::1 -j DROP
            exit 0
            """),
    },

    # ── 4.2 SSH server ─────────────────────────────────────────────────────────
    "JR2.C.4.2.2": {
        "validate_debian": _cell(
            "Verify every SSH private host key is 0600 (or stricter) and "
            "owned root:root.",
            r"""
            bad=0
            for f in /etc/ssh/ssh_host_*_key; do
              [ -e "$f" ] || continue
              [ "$(stat -c '%U:%G' "$f")" = "root:root" ] || bad=1
              case "$(stat -c '%a' "$f")" in
                600|400|0) : ;;
                *) bad=1 ;;
              esac
            done
            exit $bad
            """),
        "configure_debian": _cell(
            "Set every SSH private host key to 0600 root:root.",
            r"""
            for f in /etc/ssh/ssh_host_*_key; do
              [ -e "$f" ] || continue
              chown root:root "$f"
              chmod 0600 "$f"
            done
            exit 0
            """),
    },
    "JR2.C.4.2.4": {
        "validate_debian": _cell(
            "Verify sshd carries an explicit access policy (AllowUsers, "
            "AllowGroups, DenyUsers or DenyGroups).",
            r"""
            if command -v sshd >/dev/null 2>&1; then
              sshd -T 2>/dev/null | grep -Eqi '^(allowusers|allowgroups|denyusers|denygroups)[[:space:]]+[^[:space:]]' && exit 0
            fi
            cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | grep -Eqi '^[[:space:]]*(Allow|Deny)(Users|Groups)[[:space:]]+[^[:space:]]' && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Install a minimal explicit access policy (DenyUsers nobody) as a "
            "sshd_config.d drop-in — replace with the organisation's real "
            "allow-list. Validated with sshd -t and rolled back on error.",
            r"""
            cat /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null | grep -Eqi '^[[:space:]]*(Allow|Deny)(Users|Groups)[[:space:]]+[^[:space:]]' && exit 0
            d=/etc/ssh/sshd_config.d
            mkdir -p "$d"
            f="$d/60-sabc-access.conf"
            printf 'DenyUsers nobody\n' > "$f"
            if command -v sshd >/dev/null 2>&1 && ! sshd -t >/dev/null 2>&1; then
              rm -f "$f"
              exit 1
            fi
            systemctl reload ssh >/dev/null 2>&1 || systemctl reload sshd >/dev/null 2>&1
            exit 0
            """),
    },

    # ── 4.3 sudo ───────────────────────────────────────────────────────────────
    "JR2.C.4.3.1": {
        "validate_debian": _cell(
            "Verify sudo is installed (sudo OR sudo-ldap satisfies the "
            "control — they are alternatives, not both required).",
            r"""
            dpkg-query -W sudo >/dev/null 2>&1 && exit 0
            dpkg-query -W sudo-ldap >/dev/null 2>&1 && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Install sudo when neither alternative is present.",
            r"""
            dpkg-query -W sudo >/dev/null 2>&1 && exit 0
            dpkg-query -W sudo-ldap >/dev/null 2>&1 && exit 0
            DEBIAN_FRONTEND=noninteractive apt-get -y install sudo >/dev/null
            exit 0
            """),
    },
    "JR2.C.4.3.3": {
        "validate_debian": _cell(
            "Verify sudo is configured with a log file.",
            r"""
            grep -rEqs '^[[:space:]]*Defaults[[:space:]]+([^#]*,[[:space:]]*)?logfile[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Add Defaults logfile to a sudoers drop-in (visudo-checked, "
            "removed again on syntax error).",
            r"""
            grep -rEqs '^[[:space:]]*Defaults[[:space:]]+([^#]*,[[:space:]]*)?logfile[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null && exit 0
            f=/etc/sudoers.d/90-sabc-defaults
            printf 'Defaults logfile="/var/log/sudo.log"\n' >> "$f"
            chmod 440 "$f"
            visudo -cf "$f" >/dev/null || { rm -f "$f"; exit 1; }
            exit 0
            """),
    },
    "JR2.C.4.3.4": {
        "validate_debian": _cell(
            "Verify no sudoers rule disables re-authentication (no "
            "!authenticate tags) — no output means compliant.",
            r"""
            grep -rEs '^[^#]*\!authenticate' /etc/sudoers /etc/sudoers.d 2>/dev/null | grep -q . && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Strip !authenticate tags from sudoers files (each edit is "
            "visudo-checked and rolled back on error).",
            r"""
            files=$(grep -rEls '^[^#]*\!authenticate' /etc/sudoers /etc/sudoers.d 2>/dev/null)
            [ -n "$files" ] || exit 0
            for f in $files; do
              cp -p "$f" "$f.sabc.bak"
              sed -ri 's/[[:space:]]*\!authenticate\b//g' "$f"
              if visudo -cf "$f" >/dev/null; then
                rm -f "$f.sabc.bak"
              else
                mv "$f.sabc.bak" "$f"
              fi
            done
            exit 0
            """),
    },
    "JR2.C.4.3.5": {
        "validate_debian": _cell(
            "Verify the sudo authentication timeout is at most 15 minutes "
            "(explicit values checked; unset falls back to the compiled "
            "default reported by sudo -V).",
            r"""
            vals=$(grep -rhoPs 'timestamp_timeout[[:space:]]*=[[:space:]]*\K-?[0-9]+' /etc/sudoers /etc/sudoers.d 2>/dev/null)
            if [ -z "$vals" ]; then
              d=$(sudo -V 2>/dev/null | grep -oP 'Authentication timestamp timeout:[[:space:]]*\K-?[0-9]+')
              [ -n "$d" ] && [ "$d" -ge 0 ] && [ "$d" -le 15 ] && exit 0
              exit 1
            fi
            for v in $vals; do
              [ "$v" -ge 0 ] && [ "$v" -le 15 ] || exit 1
            done
            exit 0
            """),
        "configure_debian": _cell(
            "Set timestamp_timeout=15: rewrite oversized/disabled values in "
            "place (visudo-checked) or add an explicit default drop-in.",
            r"""
            if grep -rEqs 'timestamp_timeout[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null; then
              for f in $(grep -rEls 'timestamp_timeout[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null); do
                cp -p "$f" "$f.sabc.bak"
                sed -ri 's/(timestamp_timeout[[:space:]]*=[[:space:]]*)-?[0-9]+/\115/g' "$f"
                if visudo -cf "$f" >/dev/null; then
                  rm -f "$f.sabc.bak"
                else
                  mv "$f.sabc.bak" "$f"
                fi
              done
            else
              f=/etc/sudoers.d/90-sabc-defaults
              printf 'Defaults env_reset, timestamp_timeout=15\n' >> "$f"
              chmod 440 "$f"
              visudo -cf "$f" >/dev/null || { rm -f "$f"; exit 1; }
            fi
            exit 0
            """),
    },
    "JR2.C.4.3.6": {
        "validate_debian": _cell(
            "Verify su is restricted to an (empty) pam_wheel group.",
            r"""
            grep -Eqs '^[[:space:]]*auth[[:space:]]+(required|requisite)[[:space:]]+pam_wheel\.so[[:space:]].*use_uid.*group=' /etc/pam.d/su || exit 1
            g=$(grep -Eos 'group=[^[:space:]]+' /etc/pam.d/su | head -1 | cut -d= -f2)
            [ -n "$g" ] || exit 1
            getent group "$g" >/dev/null 2>&1 || exit 1
            [ -z "$(getent group "$g" | cut -d: -f4)" ] || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Create the empty sugroup and require pam_wheel membership for su.",
            r"""
            getent group sugroup >/dev/null 2>&1 || groupadd sugroup
            grep -Eqs '^[[:space:]]*auth[[:space:]]+(required|requisite)[[:space:]]+pam_wheel\.so' /etc/pam.d/su || \
              sed -i '/^auth[[:space:]]\+sufficient[[:space:]]\+pam_rootok\.so/a auth       required   pam_wheel.so use_uid group=sugroup' /etc/pam.d/su
            exit 0
            """),
    },

    # ── 4.4 PAM password policy (Red Hat keeps its authored overrides) ────────
    "JR2.C.4.4.1": {
        "validate_debian": _cell(
            "Verify pam_pwquality is installed and enforces minlen 14 / "
            "minclass 4.",
            r"""
            dpkg-query -W libpam-pwquality >/dev/null 2>&1 || exit 1
            v=$(grep -Ehs '^[[:space:]]*minlen[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$v" ] && [ "$v" -ge 14 ] || exit 1
            c=$(grep -Ehs '^[[:space:]]*minclass[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$c" ] && [ "$c" -ge 4 ] || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Install libpam-pwquality and set minlen 14 / minclass 4.",
            _SET_KV + r"""
            dpkg-query -W libpam-pwquality >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get -y install libpam-pwquality >/dev/null
            f=/etc/security/pwquality.conf
            [ -e "$f" ] || touch "$f"
            set_kv minlen 14 "$f"
            set_kv minclass 4 "$f"
            exit 0
            """),
    },
    "JR2.C.4.4.2": {
        "validate_debian": _cell(
            "Verify faillock is configured (deny ≤ 5, unlock_time 0 or ≥ 900) "
            "and wired into the PAM auth stack.",
            r"""
            d=$(grep -Ehs '^[[:space:]]*deny[[:space:]]*=' /etc/security/faillock.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$d" ] && [ "$d" -ge 1 ] && [ "$d" -le 5 ] || exit 1
            u=$(grep -Ehs '^[[:space:]]*unlock_time[[:space:]]*=' /etc/security/faillock.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$u" ] || exit 1
            [ "$u" -eq 0 ] || [ "$u" -ge 900 ] || exit 1
            grep -qs 'pam_faillock.so' /etc/pam.d/common-auth || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Set faillock.conf values and enable the faillock PAM profiles "
            "via pam-auth-update (the Debian-sanctioned way to edit the "
            "stack; SSH public-key logins are unaffected).",
            _SET_KV + r"""
            f=/etc/security/faillock.conf
            [ -e "$f" ] || touch "$f"
            set_kv deny 5 "$f"
            set_kv unlock_time 900 "$f"
            cat > /usr/share/pam-configs/sabc-faillock <<'PAMEOF'
Name: Enforce failed login attempt counter (faillock)
Default: yes
Priority: 0
Auth-Type: Primary
Auth:
	[default=die] pam_faillock.so authfail
Auth-Initial:
	requisite pam_faillock.so preauth
PAMEOF
            cat > /usr/share/pam-configs/sabc-faillock-notify <<'PAMEOF'
Name: Notify on failed login attempts (faillock)
Default: yes
Priority: 1024
Account-Type: Primary
Account:
	required pam_faillock.so
PAMEOF
            pam-auth-update --package >/dev/null 2>&1
            exit 0
            """),
    },

    # ── 4.5 login policy ───────────────────────────────────────────────────────
    "JR2.C.4.5.1.6": {
        "validate_debian": _cell(
            "Verify difok (changed characters in a new password) is at least 2.",
            r"""
            v=$(grep -Ehs '^[[:space:]]*difok[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$v" ] && [ "$v" -ge 2 ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set difok = 2 in pwquality.conf.",
            _SET_KV + r"""
            f=/etc/security/pwquality.conf
            [ -e "$f" ] || touch "$f"
            set_kv difok 2 "$f"
            exit 0
            """),
    },
    "JR2.C.4.5.1.7": {
        "validate_debian": _cell(
            "Verify dictionary words are rejected (dictcheck enabled).",
            r"""
            v=$(grep -Ehs '^[[:space:]]*dictcheck[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$v" ] && [ "$v" -ge 1 ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set dictcheck = 1 in pwquality.conf.",
            _SET_KV + r"""
            f=/etc/security/pwquality.conf
            [ -e "$f" ] || touch "$f"
            set_kv dictcheck 1 "$f"
            exit 0
            """),
    },
    "JR2.C.4.5.4": {
        "validate_debian": _cell(
            "Verify maxrepeat (consecutive identical characters) is 1–3.",
            r"""
            v=$(grep -Ehs '^[[:space:]]*maxrepeat[[:space:]]*=' /etc/security/pwquality.conf /etc/security/pwquality.conf.d/*.conf 2>/dev/null | tail -1 | grep -oE '[0-9]+')
            [ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 3 ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set maxrepeat = 3 in pwquality.conf.",
            _SET_KV + r"""
            f=/etc/security/pwquality.conf
            [ -e "$f" ] || touch "$f"
            set_kv maxrepeat 3 "$f"
            exit 0
            """),
    },
    "JR2.C.4.5.2": {
        "validate_debian": _cell(
            "Verify the default umask is 027 in login.defs and the profile "
            "drop-in.",
            r"""
            grep -Eqs '^[[:space:]]*UMASK[[:space:]]+027' /etc/login.defs || exit 1
            grep -Eqs '^[[:space:]]*umask[[:space:]]+027' /etc/profile.d/*.sh /etc/profile 2>/dev/null || exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Set UMASK 027 in login.defs and install a profile drop-in.",
            r"""
            if grep -Eqs '^[[:space:]]*#?[[:space:]]*UMASK[[:space:]]' /etc/login.defs; then
              sed -ri 's/^[[:space:]]*#?[[:space:]]*UMASK[[:space:]]+[0-9]+/UMASK\t\t027/' /etc/login.defs
            else
              printf 'UMASK\t\t027\n' >> /etc/login.defs
            fi
            printf 'umask 027\n' > /etc/profile.d/50-sabc-umask.sh
            chmod 644 /etc/profile.d/50-sabc-umask.sh
            exit 0
            """),
    },
    "JR2.C.4.5.3": {
        "validate_debian": _cell(
            "Verify an interactive shell timeout (TMOUT ≤ 900, non-zero) is "
            "configured.",
            r"""
            v=$(grep -Ehs 'TMOUT=' /etc/profile.d/*.sh /etc/profile /etc/bash.bashrc 2>/dev/null | grep -oE 'TMOUT=[0-9]+' | tail -1 | cut -d= -f2)
            [ -n "$v" ] && [ "$v" -ge 1 ] && [ "$v" -le 900 ] && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Install a read-only TMOUT=900 profile drop-in.",
            r"""
            printf 'TMOUT=900\nreadonly TMOUT\nexport TMOUT\n' > /etc/profile.d/50-sabc-tmout.sh
            chmod 644 /etc/profile.d/50-sabc-tmout.sh
            exit 0
            """),
    },

    # ── 5.1 logging ────────────────────────────────────────────────────────────
    "JR2.C.5.1.1.1.2": {
        "validate_debian": _cell(
            "Verify journald does not accept logs from remote clients (the "
            "systemd-journal-remote socket is absent or masked).",
            r"""
            systemctl list-unit-files 2>/dev/null | grep -q '^systemd-journal-remote\.socket' || exit 0
            [ "$(systemctl is-enabled systemd-journal-remote.socket 2>/dev/null)" = "masked" ] || exit 1
            systemctl is-active systemd-journal-remote.socket 2>/dev/null | grep -qx active && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Stop and mask the systemd-journal-remote socket and service.",
            r"""
            systemctl list-unit-files 2>/dev/null | grep -q '^systemd-journal-remote\.socket' || exit 0
            systemctl stop systemd-journal-remote.socket systemd-journal-remote.service >/dev/null 2>&1
            systemctl mask systemd-journal-remote.socket systemd-journal-remote.service >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.5.1.1.2": {
        "validate_debian": _cell(
            "Verify journald compresses large log files (effective "
            "Compress=yes).",
            r"""
            grep -Ehs '^[[:space:]]*Compress[[:space:]]*=' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null | tail -1 | grep -qi 'yes' && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set Compress=yes via a journald drop-in and restart journald.",
            r"""
            mkdir -p /etc/systemd/journald.conf.d
            f=/etc/systemd/journald.conf.d/60-sabc.conf
            grep -qs '^\[Journal\]' "$f" 2>/dev/null || printf '[Journal]\n' >> "$f"
            if grep -qs '^Compress=' "$f"; then
              sed -ri 's/^Compress=.*/Compress=yes/' "$f"
            else
              printf 'Compress=yes\n' >> "$f"
            fi
            systemctl restart systemd-journald >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.5.1.1.3": {
        "validate_debian": _cell(
            "Verify journald writes to persistent storage (effective "
            "Storage=persistent).",
            r"""
            grep -Ehs '^[[:space:]]*Storage[[:space:]]*=' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null | tail -1 | grep -qi 'persistent' && exit 0
            exit 1
            """),
        "configure_debian": _cell(
            "Set Storage=persistent via a journald drop-in (creating "
            "/var/log/journal) and restart journald.",
            r"""
            mkdir -p /etc/systemd/journald.conf.d /var/log/journal
            f=/etc/systemd/journald.conf.d/60-sabc.conf
            grep -qs '^\[Journal\]' "$f" 2>/dev/null || printf '[Journal]\n' >> "$f"
            if grep -qs '^Storage=' "$f"; then
              sed -ri 's/^Storage=.*/Storage=persistent/' "$f"
            else
              printf 'Storage=persistent\n' >> "$f"
            fi
            systemctl restart systemd-journald >/dev/null 2>&1
            exit 0
            """),
    },
    "JR2.C.5.1.2.4": {
        "validate_debian": _cell(
            "Verify rsyslog is not configured to receive logs from remote "
            "clients (no active imtcp/imudp module or input).",
            r"""
            grep -Ehs '^[[:space:]]*(module\(load="im(tcp|udp)"\)|input\(type="im(tcp|udp)"|\$ModLoad[[:space:]]+im(tcp|udp)|\$(InputTCPServerRun|UDPServerRun))' /etc/rsyslog.conf /etc/rsyslog.d/*.conf 2>/dev/null | grep -q . && exit 1
            exit 0
            """),
        "configure_debian": _cell(
            "Comment out the rsyslog remote-reception directives and restart "
            "rsyslog.",
            r"""
            changed=0
            for f in /etc/rsyslog.conf /etc/rsyslog.d/*.conf; do
              [ -e "$f" ] || continue
              if grep -Eqs '^[[:space:]]*(module\(load="im(tcp|udp)"\)|input\(type="im(tcp|udp)"|\$ModLoad[[:space:]]+im(tcp|udp)|\$(InputTCPServerRun|UDPServerRun))' "$f"; then
                sed -ri 's|^([[:space:]]*)(module\(load="im(tcp\|udp)"\).*)|\1# \2|; s|^([[:space:]]*)(input\(type="im(tcp\|udp)".*)|\1# \2|; s|^([[:space:]]*)(\$ModLoad[[:space:]]+im(tcp\|udp).*)|\1# \2|; s|^([[:space:]]*)(\$(InputTCPServerRun\|UDPServerRun).*)|\1# \2|' "$f"
                changed=1
              fi
            done
            [ "$changed" -eq 1 ] && systemctl restart rsyslog >/dev/null 2>&1
            exit 0
            """),
    },
    # Self-branching on the Debian vs Red Hat AIDE layout so the mechanical
    # Red Hat derivation keeps it correct.
    "JR2.C.5.1.3.1": {
        "validate_debian": _cell(
            "Verify AIDE monitors the audit tools with cryptographic "
            "attributes.",
            r"""
            if [ -d /etc/aide/aide.conf.d ]; then
              conf_glob='/etc/aide/aide.conf /etc/aide/aide.conf.d/*'
            else
              conf_glob='/etc/aide.conf'
            fi
            for t in auditctl auditd ausearch aureport autrace augenrules; do
              p=$(command -v "$t" 2>/dev/null || echo "/usr/sbin/$t")
              grep -Ehs "^$p[[:space:]]" $conf_glob 2>/dev/null | grep -q 'sha512' || exit 1
            done
            exit 0
            """),
        "configure_debian": _cell(
            "Add the audit tools (with p+i+n+u+g+s+b+acl+xattrs+sha512) to the "
            "AIDE configuration.",
            r"""
            if [ -d /etc/aide/aide.conf.d ]; then
              out=/etc/aide/aide.conf.d/70_sabc_audit_tools
            else
              out=/etc/aide.conf
            fi
            for t in auditctl auditd ausearch aureport autrace augenrules; do
              p=$(command -v "$t" 2>/dev/null || echo "/usr/sbin/$t")
              grep -qs "^$p[[:space:]]" "$out" 2>/dev/null || printf '%s p+i+n+u+g+s+b+acl+xattrs+sha512\n' "$p" >> "$out"
            done
            exit 0
            """),
    },

    # ── 6.1.10 /etc/opasswd permissions ───────────────────────────────────────
    "JR2.C.6.1.10": {
        "validate_debian": _cell(
            "Verify /etc/security/opasswd (and .old) is 0600 root:root when "
            "present — an absent file is compliant.",
            r"""
            for f in /etc/security/opasswd /etc/security/opasswd.old; do
              [ -e "$f" ] || continue
              [ "$(stat -c '%a %U %G' "$f")" = "600 root root" ] || exit 1
            done
            exit 0
            """),
        "configure_debian": _cell(
            "Set /etc/security/opasswd (and .old) to 0600 root:root when "
            "present.",
            r"""
            for f in /etc/security/opasswd /etc/security/opasswd.old; do
              [ -e "$f" ] || continue
              chown root:root "$f"
              chmod 0600 "$f"
            done
            exit 0
            """),
    },
}
