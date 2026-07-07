#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W ufw >/dev/null 2>&1 || exit 0
ufw status 2>/dev/null | grep -q 'Status: active' || exit 0
ufw allow in 22/tcp >/dev/null 2>&1
ufw allow out 53 >/dev/null 2>&1
ufw allow out 80/tcp >/dev/null 2>&1
ufw allow out 443/tcp >/dev/null 2>&1
ufw allow out 123/udp >/dev/null 2>&1
ufw default deny incoming >/dev/null 2>&1
ufw default deny outgoing >/dev/null 2>&1
ufw default deny routed >/dev/null 2>&1
exit 0
