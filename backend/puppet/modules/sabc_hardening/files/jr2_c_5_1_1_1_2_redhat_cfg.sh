#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop systemd-journal-remote.socket systemd-journal-remote.service 2>/dev/null || true
systemctl mask systemd-journal-remote.socket systemd-journal-remote.service 2>/dev/null || true
exit 0
