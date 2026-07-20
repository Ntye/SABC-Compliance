#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Eq '^\s*auth\s+(required|requisite)\s+pam_wheel\.so\s+([^#]*\s)?use_uid' /etc/pam.d/su
