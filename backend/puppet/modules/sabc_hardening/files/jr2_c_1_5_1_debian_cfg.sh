#!/bin/bash
shopt -s globstar 2>/dev/null || true
DEBIAN_FRONTEND=noninteractive apt-get -y install apparmor apparmor-utils >/dev/null
exit 0
