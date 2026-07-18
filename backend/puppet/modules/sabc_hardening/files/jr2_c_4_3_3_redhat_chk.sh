#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Ersq '^\s*Defaults\s+([^#]*,\s*)?logfile\s*=' /etc/sudoers /etc/sudoers.d 2>/dev/null
