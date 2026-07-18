#!/bin/bash
shopt -s globstar 2>/dev/null || true
setenforce 1 2>/dev/null || true
if [ -f /etc/selinux/config ]; then
  sed -ri 's/^[[:space:]]*SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
fi
exit 0
