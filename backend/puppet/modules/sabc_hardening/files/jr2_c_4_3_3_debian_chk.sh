#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -rEqs '^[[:space:]]*Defaults[[:space:]]+([^#]*,[[:space:]]*)?logfile[[:space:]]*=' /etc/sudoers /etc/sudoers.d 2>/dev/null && exit 0
exit 1
