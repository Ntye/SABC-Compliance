#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
systemctl unmask tmp.mount 2>/dev/null || true
systemctl enable --now tmp.mount
