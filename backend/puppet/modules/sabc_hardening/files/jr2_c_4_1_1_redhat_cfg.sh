#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
rpm -q cronie >/dev/null 2>&1 || dnf install -y cronie
systemctl unmask crond.service 2>/dev/null || true
systemctl enable --now crond.service
