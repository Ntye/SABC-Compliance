#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl is-enabled systemd-journal-remote.socket systemd-journal-remote.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active systemd-journal-remote.socket systemd-journal-remote.service 2>/dev/null | grep -q '^active' && exit 1
exit 0
