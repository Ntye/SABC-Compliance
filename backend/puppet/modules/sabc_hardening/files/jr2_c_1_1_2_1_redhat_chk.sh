#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
findmnt -kn /tmp >/dev/null 2>&1
