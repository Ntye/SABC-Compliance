#!/bin/bash
shopt -s globstar 2>/dev/null || true
grep -rEs '^[^#]*\!authenticate' /etc/sudoers /etc/sudoers.d 2>/dev/null | grep -q . && exit 1
exit 0
