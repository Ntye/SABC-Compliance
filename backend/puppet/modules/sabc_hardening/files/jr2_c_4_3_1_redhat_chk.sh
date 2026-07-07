#!/bin/bash
shopt -s globstar 2>/dev/null || true
rpm -q sudo >/dev/null 2>&1 && exit 0
rpm -q sudo-ldap >/dev/null 2>&1 && exit 0
exit 1
