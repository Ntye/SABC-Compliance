#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q rsync-daemon >/dev/null 2>&1 || {
  systemctl list-unit-files rsyncd.service 2>/dev/null | grep -q rsyncd || exit 0
}
systemctl is-enabled rsyncd.socket rsyncd.service 2>/dev/null | grep -q '^enabled' && exit 1
systemctl is-active rsyncd.socket rsyncd.service 2>/dev/null | grep -q '^active' && exit 1
exit 0
