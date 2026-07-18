#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
ss -lntu 2>/dev/null | awk '$5 !~ /^(127\.0\.0\.1|\[?::1\]?):(25|465|587)$/ && $5 ~ /:(25|465|587)$/ {found=1} END {exit found?1:0}'
