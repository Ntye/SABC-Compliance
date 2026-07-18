#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
dnf remove -y ypbind
