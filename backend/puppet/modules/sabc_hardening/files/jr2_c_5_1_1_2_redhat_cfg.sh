#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nCompress=yes\n' > /etc/systemd/journald.conf.d/60-criclo-compress.conf
systemctl restart systemd-journald.service 2>/dev/null || true
exit 0
