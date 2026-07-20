#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W ufw >/dev/null 2>&1 || exit 101
ufw status verbose 2>/dev/null | grep -q 'Status: active' || exit 1
ufw status verbose 2>/dev/null | grep -Eq 'Default: deny \(incoming\), deny \(outgoing\), (deny|disabled) \(routed\)' && exit 0
exit 1
