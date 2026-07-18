#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
command -v getenforce >/dev/null 2>&1 || exit 1
m=$(getenforce)
[ "$m" = "Enforcing" ] || [ "$m" = "Permissive" ]
