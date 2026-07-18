#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Ersq '^\s*Defaults\s+([^#]*,\s*)?use_pty\b' /etc/sudoers /etc/sudoers.d 2>/dev/null
