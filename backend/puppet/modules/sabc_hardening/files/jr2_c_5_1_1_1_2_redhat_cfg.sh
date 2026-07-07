#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files 2>/dev/null | grep -q '^systemd-journal-remote\.socket' || exit 0
systemctl stop systemd-journal-remote.socket systemd-journal-remote.service >/dev/null 2>&1
systemctl mask systemd-journal-remote.socket systemd-journal-remote.service >/dev/null 2>&1
exit 0
