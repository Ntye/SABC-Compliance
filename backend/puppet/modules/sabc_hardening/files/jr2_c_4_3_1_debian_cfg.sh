#!/bin/bash
shopt -s globstar 2>/dev/null || true
dpkg-query -W sudo >/dev/null 2>&1 && exit 0
dpkg-query -W sudo-ldap >/dev/null 2>&1 && exit 0
DEBIAN_FRONTEND=noninteractive apt-get -y install sudo >/dev/null
exit 0
