#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q chrony >/dev/null 2>&1 || dnf install -y chrony
systemctl unmask chronyd.service 2>/dev/null || true
systemctl enable --now chronyd.service
