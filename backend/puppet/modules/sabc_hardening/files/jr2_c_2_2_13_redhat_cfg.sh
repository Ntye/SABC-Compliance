#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl stop ypserv.service 2>/dev/null || true
systemctl mask ypserv.service 2>/dev/null || true
dnf remove -y ypserv
