#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
grep -Ersq '^\s*Compress=yes' /etc/systemd/journald.conf /etc/systemd/journald.conf.d 2>/dev/null
