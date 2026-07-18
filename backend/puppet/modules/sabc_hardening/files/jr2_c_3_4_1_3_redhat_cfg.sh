#!/bin/bash
shopt -s globstar 2>/dev/null || true
systemctl unmask firewalld 2>/dev/null || true
systemctl --now enable firewalld
exit 0
