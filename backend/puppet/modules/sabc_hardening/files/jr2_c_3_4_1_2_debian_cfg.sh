#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W ufw >/dev/null 2>&1 || exit 0
dpkg-query -W iptables-persistent >/dev/null 2>&1 || exit 0
DEBIAN_FRONTEND=noninteractive apt-get -y purge iptables-persistent >/dev/null
exit 0
