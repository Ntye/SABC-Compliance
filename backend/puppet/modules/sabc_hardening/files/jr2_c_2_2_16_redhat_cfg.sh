#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop rsyncd.socket rsyncd.service 2>/dev/null || true
systemctl mask rsyncd.socket rsyncd.service 2>/dev/null || true
dnf remove -y rsync-daemon 2>/dev/null || true
exit 0
