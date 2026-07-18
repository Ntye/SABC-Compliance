#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop avahi-daemon.socket avahi-daemon.service 2>/dev/null || true
systemctl mask avahi-daemon.socket avahi-daemon.service 2>/dev/null || true
dnf remove -y avahi
