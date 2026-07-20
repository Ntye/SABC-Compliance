#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl list-unit-files 2>/dev/null | grep -q '^systemd-journal-remote\.socket' || exit 0
[ "$(systemctl is-enabled systemd-journal-remote.socket 2>/dev/null)" = "masked" ] || exit 1
systemctl is-active systemd-journal-remote.socket 2>/dev/null | grep -qx active && exit 1
exit 0
