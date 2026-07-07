#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -rEqs '^[[:space:]]*Defaults[[:space:]]+([^#]*,[[:space:]]*)?logfile[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null && exit 0
f=/etc/sudoers.d/90-sabc-defaults
printf 'Defaults logfile="/var/log/sudo.log"\n' >> "$f"
chmod 440 "$f"
visudo -cf "$f" >/dev/null || { rm -f "$f"; exit 1; }
exit 0
