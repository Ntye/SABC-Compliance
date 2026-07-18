#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
for p in aide; do
  rpm -q "$p" >/dev/null 2>&1 || exit 1
done
exit 0
