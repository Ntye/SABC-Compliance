#!/usr/bin/env bash
shopt -s globstar 2>/dev/null || true
sed -ri 's/^\s*SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
setenforce 1 2>/dev/null || true
exit 0
