#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v prelink >/dev/null 2>&1 && prelink -ua 2>/dev/null || true
dnf remove -y prelink
