#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W ufw >/dev/null 2>&1 || exit 101
dpkg-query -W iptables-persistent >/dev/null 2>&1 && exit 1
exit 0
